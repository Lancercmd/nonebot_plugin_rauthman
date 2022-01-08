@echo off
python -m pip install -U pip poetry
poetry run python -m pip install -U pip
poetry install
pause