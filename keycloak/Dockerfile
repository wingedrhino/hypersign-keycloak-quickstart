FROM jboss/keycloak:9.0.0

USER root

RUN microdnf install python3 vim
ADD https://raw.githubusercontent.com/wingedrhino/DistroSetup/trunk/dotfiles/vimrc /root/.vimrc

WORKDIR /hypersign
ENV HYPERSIGN_WORKDIR /hypersign

COPY entrypoint.py /

# ENTRYPOINT ["/entrypoint.py"]
ENTRYPOINT ["sleep", "infinity"]
