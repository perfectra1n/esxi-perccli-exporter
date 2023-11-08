# Use the Python alpine image
FROM python:3.9-alpine

# Install sshpass and openssh
RUN apk add --no-cache openssh sshpass

# Copy requirements.txt to the docker image and install packages
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app

# Set the working directory to /app
WORKDIR /app

# Copy entrypoint script into the image
COPY entrypoint.sh /entrypoint.sh

# Make the script executable
RUN chmod +x /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]