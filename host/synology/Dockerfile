FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8
RUN apt-get update \
    && apt-get install --no-install-recommends -y adb fastboot usbutils ca-certificates python3 python3-serial unzip file ncurses-bin \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
CMD ["bash"]
