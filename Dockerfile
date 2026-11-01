# python image
FROM python:3.12-slim

# sets the working directory inside the container; application will run from /project, not from a folder on the host machine
WORKDIR /project

# copies the python dependencies file
COPY requirements.txt .

# installs required python libraries without storing the pip cache
RUN pip install --no-cache-dir -r requirements.txt

# copies the application code into the container
COPY app ./app

# runs the application as a non-root user
USER 10001

# starts the department simulation by default
CMD ["python", "-m", "app.department"]