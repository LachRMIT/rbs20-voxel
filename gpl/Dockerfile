# Build host for NETGEAR's Orbi-Micro GPL source. NETGEAR built it on Ubuntu 16.04 with gcc 5.
# Fixes over NETGEAR's README:
#  - OCaml is needed for the coccinelle host tool
#  - do NOT install the system "menhir": it clashes with coccinelle's bundled copy
#  - a UTF-8 locale must exist, or uClibc's gen_wc8bit writes an error into c8tables.h
FROM ubuntu:16.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
      build-essential gawk flex bison unzip zlib1g-dev libncurses5-dev gettext libssl-dev \
      subversion git python perl wget file rsync bc xz-utils bzip2 patch texinfo \
      libxml-parser-perl ccache cpio ocaml-nox ocaml-findlib camlp4 libpcre-ocaml-dev locales \
 && locale-gen en_US.UTF-8 en_US \
 && rm -rf /var/lib/apt/lists/*
ENV LANG=en_US.UTF-8
RUN useradd -m -u 1000 builder
