FROM jboss/keycloak:9.0.0

USER root

WORKDIR /hypersign

# Install Python for gruntwork and beautifulsoup4 for XML editing
# Install the ps command via procps to check for accidentally zombied processes
# Install Vim (and my .vimrc) to make life easy in the container
RUN microdnf install python3 vim procps python-lxml
RUN pip3 install beautifulsoup4 lxml
ADD https://raw.githubusercontent.com/wingedrhino/DistroSetup/trunk/dotfiles/vimrc /root/.vimrc


# Build-time environment variables!
ENV HYPERSIGN_WORKDIR=/hypersign
ENV AUTHENTICATOR_BUILD_URL='https://github.com/hypermine-bc/hs-authenticator/releases/download/v1.0.1/hs-authenticator.tar.gz'
ENV AUTHENTICATOR_TGZ_FILE='hs-authenticator.tar.gz'
ENV AUTHENTICATOR_CHECKSUM='6ce34575a1e0664e56ae6a595d49596f65cf9bee3be626906da0d421b4b459789aabe1d167365174d4f57073e99f52e4e98a9d46712db50a8bf48e436e759424'
ENV HS_THEME_FILE='hs-theme.tar.gz'
ENV HS_PLUGIN_JAR='hs-plugin-keycloak-ejb-0.2-SNAPSHOT.jar'
ENV AUTH_FLOW_NAME='hs-auth-flow'
ENV HYPERSIGN_EXECUTION_NAME='HyperSign QRCode'
ENV KCBASE='/opt/jboss/keycloak'
ENV PATH="${KCBASE}/bin:${PATH}"

COPY . .

# ENTRYPOINT ["/entrypoint.py"]
ENTRYPOINT ["sleep", "infinity"]
