# docker/Dockerfile

# Use your prebuilt base image
FROM commandjobs-base

WORKDIR /commandjobs

# Copy only your actual source code
COPY . /commandjobs

# Default command
CMD ["python3", "src/menu.py"]
