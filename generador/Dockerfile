# Usar una imagen oficial de Python ligera
FROM python:3.11-slim

WORKDIR /app

COPY . .

# Instalar las dependencias necesarias
# Usamos psycopg[binary,pool] para que no requiera compilar librerías (libpq)
RUN pip install --no-cache-dir -r requirements.txt


# Comando por defecto para ejecutar el script
CMD ["python", "main.py"]