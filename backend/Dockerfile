# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies
# - ffmpeg: Required for video and audio rendering.
# - libgl1-mesa-glx & libglib2.0-0: Required for OpenCV/PIL/PyTorch image processing if needed.
# - build-essential: Required if any package needs to compile C extensions during install.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Upgrade pip and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code
COPY . .

# Expose port 8000 for FastAPI / Uvicorn
EXPOSE 8000

# Run the FastAPI app using Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
