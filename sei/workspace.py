"""Dados pessoais locais e adaptação da rotina aos slots do CSP original."""
import json
import re
import sqlite3
from pathlib import Path
from uuid import uuid4
from contextlib import contextmanager

DIAS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom']
URGENCIAS = {1: 'Baixa', 2: 'Normal', 3: 'Alta', 4: 'Crítica'}
CORES = ['#a78bfa', '#86d993', '#76b6fa', '#f5bb73', '#f28eaf', '#64ccc5']


class Workspace:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conectar() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS subjects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    priority INTEGER NOT NULL, color TEXT NOT NULL, description TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id),
                    name TEXT NOT NULL, content BLOB NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, scope TEXT NOT NULL, role TEXT NOT NULL,
                    content TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')
            if 'urgency' not in {r['name'] for r in db.execute('PRAGMA table_info(subjects)')}:
                db.execute('ALTER TABLE subjects ADD COLUMN urgency INTEGER NOT NULL DEFAULT 2')
            if 'origin' not in {r['name'] for r in db.execute('PRAGMA table_info(files)')}:
                db.execute("ALTER TABLE files ADD COLUMN origin TEXT NOT NULL DEFAULT 'Enviado'")
            if db.execute("SELECT 1 FROM settings WHERE key='config'").fetchone() is None:
                nomes = ['Inteligência Artificial', 'Banco de Dados', 'Ciência de Dados', 'Engenharia de Software']
                ids = [uuid4().hex for _ in nomes]
                for i, (nome, peso) in enumerate(zip(nomes, [3, 2, 3, 1])):
                    db.execute('INSERT INTO subjects(id,name,priority,color,description) VALUES (?,?,?,?,?)',
                               (ids[i], nome, peso, CORES[i], ''))
                config = {'profile': 'original', 'duration': 60, 'limit': 2, 'notes': '',
                          'routine': [{'Dia': d, 'Estudar': d not in ['Sab', 'Dom'], 'Início estudo': '19:00',
                                       'Fim estudo': '21:00', 'Trabalha': d not in ['Sab', 'Dom'],
                                       'Início trabalho': '09:00', 'Fim trabalho': '17:00'} for d in DIAS],
                          'classes': [{'subject': ids[0], 'day': 'Seg', 'start': '18:00', 'end': '19:00'},
                                      {'subject': ids[1], 'day': 'Qua', 'start': '18:00', 'end': '19:00'}]}
                db.execute('INSERT INTO settings VALUES (?,?)', ('config', json.dumps(config)))
                db.execute('INSERT INTO settings VALUES (?,?)', ('plan_status', json.dumps('initial')))
            # Migração preserva os cadastros e a rotina já existentes.
            row = db.execute("SELECT value FROM settings WHERE key='config'").fetchone()
            cfg = json.loads(row['value'])
            if len(cfg['routine']) == 5:
                cfg['routine'] += [{'Dia': d, 'Estudar': False, 'Início estudo': '09:00',
                                    'Fim estudo': '12:00', 'Trabalha': False,
                                    'Início trabalho': '09:00', 'Fim trabalho': '17:00'} for d in ['Sab', 'Dom']]
                db.execute("UPDATE settings SET value=? WHERE key='config'", (json.dumps(cfg),))
            if db.execute("SELECT 1 FROM messages WHERE scope='global'").fetchone():
                cid = uuid4().hex
                db.execute('INSERT INTO conversations(id,title) VALUES (?,?)', (cid, 'Conversa anterior'))
                db.execute("UPDATE messages SET scope=? WHERE scope='global'", (cid,))

    @contextmanager
    def conectar(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, key, default=None):
        with self.conectar() as db:
            row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default

    def set(self, key, value):
        with self.conectar() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value, ensure_ascii=False)))

    def invalidate(self):
        self.set('plan', None)
        self.set('error', None)
        self.set('plan_status', 'pending')

    def subjects(self):
        with self.conectar() as db:
            return [dict(r) for r in db.execute('SELECT * FROM subjects ORDER BY rowid')]

    def save_subject(self, name, priority, color, description='', subject_id=None, urgency=2):
        name = name.strip()
        if not name or '__' in name:
            raise ValueError('Informe um nome de matéria sem "__".')
        if any(s['name'].casefold() == name.casefold() and s['id'] != subject_id for s in self.subjects()):
            raise ValueError('Já existe uma matéria com esse nome.')
        if not 1 <= int(priority) <= 10 or urgency not in URGENCIAS or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Use prioridade de 1 a 10 e uma cor válida.')
        sid = subject_id or uuid4().hex
        with self.conectar() as db:
            if subject_id:
                db.execute('UPDATE subjects SET name=?,priority=?,color=?,description=?,urgency=? WHERE id=?',
                           (name, int(priority), color, description, urgency, sid))
            else:
                db.execute('INSERT INTO subjects(id,name,priority,color,description,urgency) VALUES (?,?,?,?,?,?)',
                           (sid, name, int(priority), color, description, urgency))
        self.invalidate()
        return sid

    def save_config(self, config):
        validar_config(config, self.subjects())
        self.set('config', config)
        self.invalidate()

    def files(self, sid):
        with self.conectar() as db:
            return [dict(r) for r in db.execute('SELECT id,name,origin,length(content) AS size FROM files WHERE subject_id=? ORDER BY created,id', (sid,))]

    def add_file(self, sid, name, content, origin='Enviado'):
        if not content or len(content) > 10 * 1024 * 1024:
            raise ValueError('Cada arquivo deve ter conteúdo e no máximo 10 MB.')
        name = name.replace('\\', '/').split('/')[-1]
        with self.conectar() as db:
            if db.execute('SELECT 1 FROM files WHERE subject_id=? AND name=? AND content=?', (sid, name, content)).fetchone():
                return
            db.execute('INSERT INTO files(id,subject_id,name,content,origin) VALUES (?,?,?,?,?)',
                       (uuid4().hex, sid, name, content, origin))

    def file_content(self, fid):
        with self.conectar() as db:
            return bytes(db.execute('SELECT content FROM files WHERE id=?', (fid,)).fetchone()['content'])

    def messages(self, scope):
        with self.conectar() as db:
            return [dict(r) for r in db.execute('SELECT role,content FROM messages WHERE scope=? ORDER BY id', (scope,))]

    def message(self, scope, role, content):
        with self.conectar() as db:
            db.execute('INSERT INTO messages(scope,role,content) VALUES (?,?,?)', (scope, role, content))
            if role == 'user':
                db.execute("UPDATE conversations SET title=? WHERE id=? AND title='Nova conversa'", (content[:55], scope))

    def conversations(self):
        with self.conectar() as db:
            return [dict(r) for r in db.execute('SELECT * FROM conversations ORDER BY rowid DESC')]

    def new_conversation(self):
        cid = uuid4().hex
        with self.conectar() as db:
            db.execute('INSERT INTO conversations(id,title) VALUES (?,?)', (cid, 'Nova conversa'))
        return cid

    def edit_study(self, subject_id, day, start, original=None, remove=False):
        """Ajuste manual da semana, respeitando rotina, conflitos e limite diário."""
        config, plan = self.get('config'), self.get('plan')
        if not plan or not plan['viavel']:
            raise ValueError('Gere um plano válido antes de editar os estudos.')
        agenda = dict(plan['cronograma'])
        if original and original not in agenda:
            raise ValueError('Esta sessão não existe mais. Atualize o calendário.')
        if original:
            del agenda[original]
        if not remove:
            subject = next((s for s in self.subjects() if s['id'] == subject_id), None)
            if not subject or day not in DIAS:
                raise ValueError('Selecione uma matéria e um dia válidos.')
            slot = f'{day} {start}'
            inicio, duracao = minutos(start), config['duration']
            row = next(r for r in config['routine'] if r['Dia'] == day)
            bloqueios = bloqueios_dia(config, day)
            if not any(a <= inicio and inicio + duracao <= b for a,b in study_intervals(row)) or any(
                    sobrepoe(inicio, inicio + duracao, a, b) for a, b in bloqueios):
                raise ValueError('Este horário não está livre na sua disponibilidade.')
            if any(d == day and sobrepoe(inicio, inicio + duracao, minutos(h), minutos(h) + duracao)
                   for d, h in (v.split() for v in agenda.values())):
                raise ValueError('Já existe um estudo nesse horário.')
            if sum(v.startswith(day + ' ') for v in agenda.values()) >= config['limit']:
                raise ValueError('O limite de sessões desse dia foi atingido.')
            i = 1
            while f'{subject["name"]}__{i}' in agenda:
                i += 1
            agenda[f'{subject["name"]}__{i}'] = slot
        presentes = {s.rsplit('__', 1)[0] for s in agenda}
        plan.update(cronograma=agenda, manual=True,
                    disciplinas_sem_horario=[s['name'] for s in self.subjects() if s['name'] not in presentes])
        self.set('plan', plan)


def minutos(hora):
    if not isinstance(hora, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', hora):
        raise ValueError('Use horários no formato HH:MM, entre 00:00 e 23:59.')
    h, m = map(int, hora.split(':'))
    return h * 60 + m


def horario(valor):
    # A meia-noite continua sendo 1440 nos cálculos, mas é exibida como 00:00.
    valor %= 1440
    return f'{valor // 60:02d}:{valor % 60:02d}'


def fim_minutos(hora):
    """00:00 no campo de fim representa a meia-noite que encerra o dia."""
    return 1440 if hora in ('00:00', '24:00') else minutos(hora)


def study_intervals(row):
    if not row['Estudar']:
        return []
    if 'study_slots' not in row:
        return [(minutos(row['Início estudo']), fim_minutos(row['Fim estudo']))]
    pontos = sorted({minutos(h) for h in row['study_slots']})
    periodos = []
    for p in pontos:
        if periodos and periodos[-1][1] == p:
            periodos[-1] = (periodos[-1][0], p + 30)
        else:
            periodos.append((p, p + 30))
    return periodos


def bloqueios_dia(config, day):
    row = next(r for r in config['routine'] if r['Dia'] == day)
    blocos = [(minutos(a['start']), fim_minutos(a['end'])) for a in config['classes'] if a['day'] == day]
    blocos += [(minutos(a['start']), fim_minutos(a['end'])) for a in config.get('commitments', []) if a['day'] == day]
    if row['Trabalha']:
        blocos.append((minutos(row['Início trabalho']), fim_minutos(row['Fim trabalho'])))
    return blocos


def sobrepoe(a, b, c, d):
    return a < d and c < b


def validar_config(config, subjects):
    if config['duration'] not in [30, 60, 90, 120] or not 1 <= config['limit'] <= 48:
        raise ValueError('Duração ou limite diário inválido.')
    if len(config['routine']) != 7 or [r['Dia'] for r in config['routine']] != DIAS:
        raise ValueError('A rotina deve conter segunda a domingo, na ordem.')
    for r in config['routine']:
        if 'study_slots' in r:
            if not isinstance(r['study_slots'], list) or any(minutos(h) % 30 for h in r['study_slots']):
                raise ValueError('Selecione blocos de estudo alinhados a 30 minutos.')
            if len(set(r['study_slots'])) != len(r['study_slots']):
                raise ValueError('Há horários de estudo repetidos.')
        elif r['Estudar'] and minutos(r['Início estudo']) >= fim_minutos(r['Fim estudo']):
            raise ValueError(f"{r['Dia']}: o fim do estudo deve ser depois do início.")
        if r['Trabalha'] and minutos(r['Início trabalho']) >= fim_minutos(r['Fim trabalho']):
            raise ValueError(f"{r['Dia']}: o fim do trabalho deve ser depois do início.")
    ids = {s['id'] for s in subjects}
    for i, aula in enumerate(config['classes']):
        if aula['subject'] not in ids or aula['day'] not in DIAS:
            raise ValueError('Selecione uma matéria cadastrada e um dia válido para cada aula.')
        inicio, fim = minutos(aula['start']), fim_minutos(aula['end'])
        if inicio >= fim:
            raise ValueError('O fim da aula deve ser depois do início.')
        for outra in config['classes'][:i]:
            if aula['day'] == outra['day'] and sobrepoe(inicio, fim, minutos(outra['start']), fim_minutos(outra['end'])):
                raise ValueError('Há aulas sobrepostas no mesmo dia.')
    for c in config.get('commitments', []):
        if c['day'] not in DIAS or not isinstance(c['title'], str) or not c['title'].strip():
            raise ValueError('Informe o dia e o nome de cada compromisso.')
        if minutos(c['start']) >= fim_minutos(c['end']):
            raise ValueError('O fim do compromisso deve ser depois do início.')


def slots_disponiveis(config):
    """Sessões sem sobreposição, descontando trabalho e aulas antes do CSP."""
    slots = []
    duracao = config['duration']
    for r in config['routine']:
        if not r['Estudar']:
            continue
        bloqueios = bloqueios_dia(config, r['Dia'])
        for a, b in study_intervals(r):
            for inicio in range(a, b - duracao + 1, duracao):
                if not any(sobrepoe(inicio, inicio + duracao, c, d) for c, d in bloqueios):
                    slots.append(f"{r['Dia']} {horario(inicio)}")
    return slots
