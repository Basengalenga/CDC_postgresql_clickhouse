FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

# 1. Copiar tu script específico
COPY . .

EXPOSE 8501

# 2. Ejecutar ese script
CMD ["streamlit", "run", "main.py"]