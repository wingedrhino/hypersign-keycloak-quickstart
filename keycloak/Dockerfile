FROM jboss/keycloak:9.0.0

USER root

WORKDIR /hypersign

# Install Python for grunt work and beautifulsoup4 for XML editing
# Install the ps command via procps to check for accidentally zombied processes
# Install Vim (and my .vimrc) to make life easy in the container
RUN microdnf install python3 vim procps
ADD https://raw.githubusercontent.com/wingedrhino/DistroSetup/trunk/dotfiles/vimrc /root/.vimrc

# Build-time environment variables!
ENV AUTHENTICATOR_BUILD_URL='https://github.com/hypermine-bc/hs-authenticator/releases/download/v1.0.1/hs-authenticator.tar.gz'
ENV AUTHENTICATOR_CHECKSUM='6ce34575a1e0664e56ae6a595d49596f65cf9bee3be626906da0d421b4b459789aabe1d167365174d4f57073e99f52e4e98a9d46712db50a8bf48e436e759424'

# Don't change these environment variables
ENV KCBASE='/opt/jboss/keycloak'
ENV KC_EXECUTION_STRATEGY='docker'
ENV PATH="${KCBASE}/bin:${PATH}"
ENV KC_BASEURL='http://localhost:8080'
ENV KEYCLOAK_MODE='standalone-ha'

COPY . .

# ENTRYPOINT ["/entrypoint.py"]
ENTRYPOINT ["sleep", "infinity"]
