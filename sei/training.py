"""Pré-processamento e treinamento reproduzíveis, conforme o notebook."""
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from .schema import FEATURES, CATEGORICAL


def criar_pipeline():
    return Pipeline([
        ('preprocessamento', ColumnTransformer([
            ('categoricas', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL),
            ('numericas', StandardScaler(), [c for c in FEATURES if c not in CATEGORICAL])])),
        ('modelo', LogisticRegression(max_iter=2000, random_state=42))])


def treinar(df):
    X, y = df[FEATURES].copy(), df['Target'].copy()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y)
    pipeline = criar_pipeline()
    pipeline.fit(X_train, y_train)
    return pipeline, X_train, X_test, y_train, y_test
