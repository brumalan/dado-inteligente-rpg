# Dado inteligente para RPG de mesa

Trabalho final da disciplina Database Of Things (270400), UPF. Alan Brum, 92305.

Um ESP-32 rola dados de RPG (d4 a d20), mostra o resultado num LCD 16x2 e registra cada rolagem
numa API REST em FastAPI, que grava no MongoDB e devolve histórico e estatísticas por personagem e por sessão.

- `main.py` e `modelos.py`: API (FastAPI + MongoEngine). O endereço do banco vem da variável `MONGO_URI`.
- `personagens_iniciais.py`: fichas gravadas na primeira subida, se a coleção estiver vazia.
- `simulador_esp32.py`: faz as mesmas chamadas do firmware, para testar sem o hardware.
- `firmware/`: sketches do ESP-32 (projeto, teste das saídas e scanner I2C).

Render: build `pip install -r requirements.txt`, start `uvicorn main:app --host 0.0.0.0 --port $PORT`.
