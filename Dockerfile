# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed by OpenCV
RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application's code into the container
COPY . .

# Command to run the application using Gunicorn
# It will run the 'app' object from the 'main.py' file
# We use multiple workers and threads to handle concurrent requests
CMD ["gunicorn", "--workers=2", "--threads=4", "--bind=0.0.0.0:10000", "main:app"]
