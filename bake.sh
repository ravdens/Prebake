#!/bin/bash
date > speed.txt
docker buildx bake --load -f docker.hcl group1 && \
docker buildx bake --load -f docker.hcl group2 && \
docker buildx bake --load -f docker.hcl group3 && \
docker buildx bake --load -f docker.hcl group4 && \
docker buildx bake --load -f docker.hcl group5 && \
docker buildx bake --load -f docker.hcl group6
date >> speed.txt