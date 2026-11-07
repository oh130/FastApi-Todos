FROM eclipse-temurin:17-jre-jammy

ENV JMETER_VERSION=5.6.3
ENV JMETER_HOME=/opt/apache-jmeter-${JMETER_VERSION}
ENV PATH=${JMETER_HOME}/bin:$PATH

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    cd /tmp; \
    curl -fsSL -o jmeter.tgz    "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz"; \
    curl -fsSL -o jmeter.sha512 "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz.sha512"; \
    EXPECTED="$(tr -d ' \n' < jmeter.sha512 | sed 's/.*://' | grep -oE '[0-9a-fA-F]{128}' | head -1 | tr 'A-Z' 'a-z')"; \
    ACTUAL="$(sha512sum jmeter.tgz | cut -d' ' -f1)"; \
    [ "$EXPECTED" = "$ACTUAL" ] || { echo "checksum mismatch: $ACTUAL != $EXPECTED"; exit 1; }; \
    tar -xzf jmeter.tgz -C /opt/; \
    rm -f jmeter.tgz jmeter.sha512

RUN useradd -u 1000 -m -s /bin/bash jmeter && \
    mkdir -p /jmeter && chown -R jmeter:jmeter /jmeter ${JMETER_HOME}

USER jmeter

WORKDIR /jmeter

CMD ["jmeter", "-n"]
