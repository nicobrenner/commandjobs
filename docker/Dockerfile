# Use an official Python runtime as a parent image
FROM python:3.12

# Copy the current directory contents into the container at /app
COPY . /commandjobs

# Set the working directory in the container
WORKDIR /commandjobs

# Install any needed packages specified in requirements.txt
RUN pip3 install --no-cache-dir -r config/requirements.txt

# Run menu.py when the container launches
CMD ["python3", "src/menu.py"]

