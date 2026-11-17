FEATURES = ['Application mode', 'Application order', 'Course', 'Daytime/evening attendance', 'Previous qualification', 'Previous qualification (grade)', 'Admission grade', 'Displaced', 'Educational special needs', 'Debtor', 'Tuition fees up to date', 'Scholarship holder', 'Age at enrollment', 'Curricular units 1st sem (credited)', 'Curricular units 1st sem (enrolled)', 'Curricular units 1st sem (evaluations)', 'Curricular units 1st sem (approved)', 'Curricular units 1st sem (grade)', 'Curricular units 1st sem (without evaluations)', 'Unemployment rate', 'Inflation rate', 'GDP']
CATEGORICAL = ['Application mode', 'Course', 'Previous qualification']
# Preferências fornecidas pelo estudante.
# Elas NÃO vêm do dataset, pois o dataset não possui dificuldade por disciplina.
prioridades_disciplinas = {
    "Inteligencia Artificial": 3,
    "Ciencia de Dados": 3,
    "Banco de Dados": 2,
    "Engenharia de Software": 1,
}

horarios_disponiveis = [
    "Seg 19:00", "Seg 20:00",
    "Ter 19:00", "Ter 20:00",
    "Qua 19:00", "Qua 20:00",
    "Qui 19:00", "Qui 20:00",
    "Sex 19:00", "Sex 20:00",
]

MAX_SESSOES_POR_DIA = 2