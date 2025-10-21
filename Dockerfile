# Use an official Python runtime as a parent image
FROM python:3.12.7-slim

# Install system dependencies for tesseract-ocr and poppler-utils
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the current directory contents into the container
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port (Render sets PORT dynamically)
ENV PORT=8080
EXPOSE $PORT

# Run the Streamlit app, using the PORT environment variable
CMD ["sh", "-c", "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"]
