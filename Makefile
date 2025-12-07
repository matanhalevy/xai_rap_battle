.PHONY: setup run

setup:
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

run:
	. venv/bin/activate && uvicorn app_gradio_fastapi.main:app --host 0.0.0.0 --port 7860 --reload
