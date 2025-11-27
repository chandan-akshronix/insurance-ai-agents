ARG scannerVersion=0.0.23

ARG runModuleAsEntryPoint
ARG pythonEntryPointFile

#Non Root User Configuration
RUN addgroup --system --gid 10001 appgrp \
    && adduser --system --uid 10000 --shell /bin/nologin --home /opt/app/ --ingroup appgrp app
    

RUN sed -i 's/CipherString = DEFAULT@SECLEVEL=2/CipherString = DEFAULT@SECLEVEL=1/' /usr/lib/ssl/openssl.cnf
RUN apt-get update -y --fix-missing && apt-get install -y curl gcc gnupg unixodbc unixodbc-dev freetds-dev libssl-dev

USER 10000

ENV runModuleEntryPoint=${runModuleAsEntryPoint}
ENV pythonEntryPoint=${pythonEntryPointFile}

COPY . /opt/app
WORKDIR /opt/app

# Artifactory PyPi Repository
RUN pip install -r requirements.txt

# Files directory to use for upload in Ephemeral Storage
RUN mkdir /opt/app/files
RUN chown -R 10000:10001 /opt/app/files
RUN touch /opt/app/entrypoint.sh && \
    echo "export PYTHONPATH=/opt/app/app_server" >> /opt/app/entrypoint.sh && \
    echo "python -m fastapi run --host 0.0.0.0 --port 8080 app_server/app.py" >> /opt/app/entrypoint.sh
RUN chmod +x /opt/app/entrypoint.sh
####################################################################
# Execute Tests
FROM build as test
ARG skipCodeCoverage

WORKDIR /opt/app

RUN if [ "$skipCodeCoverage" = "false" ]; then \
        python -m coverage run -m pytest -rap --junitxml coverage.xml && \
        python -m coverage xml -i; \
    fi

FROM build as run
WORKDIR /opt/app
EXPOSE 8080
ENTRYPOINT ["/bin/sh", "/opt/app/entrypoint.sh"]
