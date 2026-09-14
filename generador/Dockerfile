# Usar una imagen oficial de Python ligera
FROM python:3.11-slim

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar las dependencias necesarias
# Usamos psycopg[binary,pool] para que no requiera compilar librerías (libpq)
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el script de Python al directorio de trabajo del contenedor
COPY . .

# Comando por defecto para ejecutar el script
CMD ["python", "main.py"]