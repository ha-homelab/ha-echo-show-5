FROM debian:bookworm-slim@sha256:e67eeead736ff7bbe258ef088bff683635c561b1fcfefad0806c1df4ab49ce0e
RUN apt-get update \
    && apt-get install --no-install-recommends -y adb fastboot usbutils ca-certificates python3 python3-serial unzip file ncurses-bin \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
CMD ["bash"]
