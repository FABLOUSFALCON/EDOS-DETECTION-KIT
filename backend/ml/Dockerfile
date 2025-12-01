# SIMPLE BEAST MODE DOCKER CONTAINER
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    curl gcc g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy the WORKING Beast Mode files
COPY beast_mode_api.py .
COPY beast_mode_inference.py .
COPY requirements_minimal.txt ./requirements.txt
COPY data/06_models/trained_impafs_model.pkl ./data/06_models/
COPY conf/ ./conf/

# Install packages
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 23333

# Run the PROVEN working API
CMD ["python", "beast_mode_api.py"]
