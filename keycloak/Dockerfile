FROM jboss/keycloak:9.0.0

USER root

ENV PATH="${KCBASE}/bin:${PATH}"

WORKDIR /hypersign

# Application would fail if this isn't set!
ENV HYPERSIGN_WORKDIR /hypersign

# Install Python - which we need
# Install Vim (and my .vimrc) to make life easy
# Install the ps command via procps to make debugging better
RUN microdnf install python3 vim procps
ADD https://raw.githubusercontent.com/wingedrhino/DistroSetup/trunk/dotfiles/vimrc /root/.vimrc


COPY entrypoint.py .

# ENTRYPOINT ["/entrypoint.py"]
ENTRYPOINT ["sleep", "infinity"]
