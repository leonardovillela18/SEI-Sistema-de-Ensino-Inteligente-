"""Demonstração offline do fluxo completo."""
import argparse
import json
from pathlib import Path
import joblib
from sei.schema import prioridades_disciplinas, horarios_disponiveis
from sei.service import executar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artefatos', type=Path, default=Path('artefatos'))
    parser.add_argument('--perfil', default='original')
    parser.add_argument('--horarios', type=int, choices=[2, 10], default=10)
    args = parser.parse_args()
    try:
        modelo = joblib.load(args.artefatos / 'pipeline.joblib')
        perfis = json.loads((args.artefatos / 'perfis.json').read_text(encoding='utf-8'))
        if args.perfil not in perfis:
            parser.error(f'Perfil inexistente; opções: {list(perfis)}')
        resultado = executar(modelo, perfis[args.perfil], prioridades_disciplinas,
                             horarios_disponiveis[:args.horarios])
    except (FileNotFoundError, ValueError) as exc:
        parser.exit(1, f'Erro: {exc}. Execute preparar.py se faltarem artefatos.\n')
    ml = resultado['ml']
    print(f"Classe: {ml['classe_predita']} | Evasão: {ml['probabilidade_dropout']:.8%}")
    print(f"Risco: {ml['nivel_risco']} | Sessões semanais: {ml['sessoes_semanais']}")
    print('Agenda válida.' if resultado['viavel'] else 'Agenda inviável com as restrições atuais.')
    for sessao, horario in (resultado['cronograma'] or {}).items():
        print(f'  {horario}: {sessao}')
    print('Disciplinas sem horário:', ', '.join(resultado['disciplinas_sem_horario']) or 'nenhuma')


if __name__ == '__main__':
    main()
