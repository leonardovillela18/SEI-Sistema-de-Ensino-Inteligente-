"""Entrada pública: banco temporário exclusivo de cada sessão do navegador."""
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from app import main


if '_demo_directory' not in st.session_state:
    # Manter o objeto na sessão mantém a pasta viva durante os reruns.
    # TemporaryDirectory remove os dados quando a sessão é coletada.
    directory = Path(__file__).resolve().parent / 'dados' / 'sessoes'
    directory.mkdir(parents=True, exist_ok=True)
    st.session_state['_demo_directory'] = TemporaryDirectory(
        prefix='sei-demo-', dir=directory, ignore_cleanup_errors=True)

main(db_path=Path(st.session_state['_demo_directory'].name) / 'sei.db', demo=True)
