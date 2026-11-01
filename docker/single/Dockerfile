# Unpress engine image — a self-contained bench with frappe + builder +
# wp_migrator + unpress_core + blog. Built by scripts/build-image.sh (which
# stages the build context, including the builder fork's `unpress` branch).
#
# Pinned by digest, not `latest`: in 2026-11 that tag moved to Debian trixie,
# whose MariaDB client insists on TLS. The `mariadb:10.6` in compose.yaml offers
# none, so the container waited for its database forever. Moving this digest is
# a decision: check that client against that server first.
FROM frappe/bench@sha256:6df74bce06ab017aa350a16ffdc7aff4559a4a1bf3d785d8e552dacc19b5f0e7

# Links the published package to its source on the package page. GHCR uses it
# when a package is first created; an existing package keeps whatever repository
# it was linked to, which has to be changed in the package settings.
LABEL org.opencontainers.image.source="https://github.com/neoserviceai/unpress"
LABEL org.opencontainers.image.licenses="AGPL-3.0"

USER frappe
WORKDIR /home/frappe

RUN bench init --skip-redis-config-generation --frappe-branch version-16 frappe-bench

WORKDIR /home/frappe/frappe-bench

# app sources staged into the build context by scripts/build-image.sh.
# builder is copied (and its editor built) before the unpress apps so python
# app changes never invalidate the expensive yarn layer.
COPY --chown=frappe:frappe ctx/builder apps/builder

# upstream builder does not commit built frontend assets (the v15 fork did):
# build the editor here, then drop node_modules so the layer stays lean
RUN cd apps/builder/frontend && yarn install --silent && yarn build \
	&& rm -rf node_modules ../frappe-ui/node_modules /home/frappe/.cache/yarn \
	&& rm -rf /home/frappe/.cache/Cypress
# Cypress is a dev dependency of the editor's test setup; `yarn install` puts
# its binary in ~/.cache/Cypress, outside the yarn cache this line used to be
# the only thing clearing. It was riding along in every published image, and it
# is what filled the CI runner's disk.

# The blog: frappe's own Blog module, carved out of the core in v16 and
# shipped as an app. Taken from our own fork, which currently holds exactly
# what upstream holds.
#
# That the fork does not diverge is not an argument for dropping it — it was
# dropped once on that reasoning and put back. `version-16` upstream is a
# moving branch: without a fork, whatever frappe pushes lands in the next image
# we publish, and we find out from a user. The fork is where we decide WHEN to
# take their changes. Sync it deliberately:
#
#     git -C blog fetch upstream && git -C blog merge upstream/version-16
#
# It is a plugin — installed here, and the site owner turns it on or off from
# the Studio (see unpress_core/plugins.py).
ARG BLOG_REPO=https://github.com/neoserviceai/blog
ARG BLOG_BRANCH=version-16
RUN git clone --depth 1 --branch "$BLOG_BRANCH" "$BLOG_REPO" apps/blog \
	&& rm -rf apps/blog/.git

COPY --chown=frappe:frappe ctx/wp_migrator apps/wp_migrator
COPY --chown=frappe:frappe ctx/unpress_core apps/unpress_core

RUN ./env/bin/pip install --no-cache-dir -e apps/builder -e apps/wp_migrator -e apps/unpress_core -e apps/blog \
	&& printf "frappe\nbuilder\nwp_migrator\nunpress_core\nblog\n" > sites/apps.txt \
	&& mkdir -p sites/assets \
	&& ln -sfn ../../apps/builder/builder/public sites/assets/builder \
	&& ln -sfn ../../apps/unpress_core/unpress_core/public sites/assets/unpress_core \
	&& ln -sfn ../../apps/wp_migrator/wp_migrator/public sites/assets/wp_migrator \
	&& ln -sfn ../../apps/blog/blog/public sites/assets/blog

COPY --chown=frappe:frappe docker/single/Procfile.prod Procfile
COPY --chown=frappe:frappe docker/single/entrypoint.sh /home/frappe/entrypoint.sh

ENV FRAPPE_BENCH_PATH=/home/frappe/frappe-bench

EXPOSE 8000 9000
CMD ["bash", "/home/frappe/entrypoint.sh"]
