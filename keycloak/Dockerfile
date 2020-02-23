FROM jboss/keycloak:9.0.0

USER root

RUN microdnf install python3 vim
ADD https://raw.githubusercontent.com/wingedrhino/DistroSetup/trunk/dotfiles/vimrc /root/.vimrc

WORKDIR /hypersign
# Application would fail if this isn't set!
ENV HYPERSIGN_WORKDIR /hypersign

ADD https://github.com/hypermine-bc/hs-authenticator/releases/download/v1.0.1/hs-authenticator.tar.gz .

COPY entrypoint.py .

# ENTRYPOINT ["/entrypoint.py"]
ENTRYPOINT ["sleep", "infinity"]
