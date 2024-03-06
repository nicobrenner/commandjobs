# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /repo

# Copy the current directory contents into the container at /app
COPY . /repo

# Install any needed packages specified in requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Run menu.py when the container launches
CMD ["python3", "/repo/src/menu.py"]

