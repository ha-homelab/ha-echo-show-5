FROM debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc
RUN apt-get update \
    && apt-get install --no-install-recommends -y adb fastboot usbutils ca-certificates python3 python3-serial unzip file ncurses-bin \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
CMD ["bash"]
