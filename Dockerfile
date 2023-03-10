FROM python:3.10
WORKDIR /app
COPY requirements.txt requirements.txt
COPY admins_id.txt admins_id.txt
RUN python3 -m pip install --upgrade pip
RUN pip install -r requirements.txt
COPY . .