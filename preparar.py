"""Preparação online (ou via CSV local) dos artefatos da apresentação."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sei.schema import FEATURES, CATEGORICAL
from sei.core import gerar_saida_ml
from sei.training import treinar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dados', type=Path, help='CSV preparado anteriormente, contendo Target')
    parser.add_argument('--saida', type=Path, default=Path('artefatos'))
    args = parser.parse_args()
    if args.dados:
        df = pd.read_csv(args.dados)
    else:
        from ucimlrepo import fetch_ucirepo
        try:
            dataset = fetch_ucirepo(id=697)
        except ConnectionError as exc:
            parser.exit(1, f'Falha no download UCI: {exc}. Use --dados fontes/uci_697.csv para preparar offline.\n')
        df = dataset.data.features.copy()
        df['Target'] = dataset.data.targets.iloc[:, 0]
    pipeline, X_train, X_test, y_train, y_test = treinar(df)
    args.saida.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, args.saida / 'pipeline.joblib')
    # Mantém a ordem e os índices: o perfil original é exatamente X_test.iloc[0].
    perfis = {'original': X_test.iloc[[0]].to_dict(orient='records')[0]}
    indices = {'original': int(X_test.index[0])}
    for classe in pipeline.classes_:
        linha = X_test.loc[y_test == classe].iloc[0]
        perfis[classe.lower()] = X_test.loc[[linha.name]].to_dict(orient='records')[0]
        indices[classe.lower()] = int(linha.name)
    def salvar(nome, objeto):
        (args.saida / nome).write_text(json.dumps(objeto, ensure_ascii=False, indent=2), encoding='utf-8')
    salvar('perfis.json', perfis)
    df[FEATURES + ['Target']].to_csv(args.saida / 'dados.csv', index=False)
    salvar('divisao.json', {'treino': X_train.index.tolist(), 'teste': X_test.index.tolist()})
    pred = pipeline.predict(X_test)
    salvar('metadados.json', {
        'fonte': 'UCI 697; notebook células 14, 26, 28, 47, 53, 55–65',
        'features': FEATURES, 'categoricas': CATEGORICAL,
        'test_size': 0.2, 'random_state': 42, 'stratify': 'Target',
        'modelo': 'LogisticRegression(max_iter=2000, random_state=42), demais parâmetros padrão',
        'tamanho_treino': len(X_train), 'tamanho_teste': len(X_test),
        'indices_perfis': indices,
        'versoes': {p: importlib.metadata.version(p) for p in ['numpy', 'pandas', 'scikit-learn', 'joblib', 'ucimlrepo']},
        'sha256_dados': hashlib.sha256((args.saida / 'dados.csv').read_bytes()).hexdigest(),
        'acuracia_teste': accuracy_score(y_test, pred),
        'f1_macro_teste': f1_score(y_test, pred, average='macro'),
        'saida_original': gerar_saida_ml(pipeline, X_test.iloc[[0]]),
        'probabilidade_notebook': 0.018754408201636767,
        'diferenca_pontos_percentuais': 100 * (gerar_saida_ml(pipeline, X_test.iloc[[0]])['probabilidade_dropout'] - 0.018754408201636767)})
    print((args.saida / 'metadados.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    main()
