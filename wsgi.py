"""WSGI entry point for deployment providers."""

from segmenta_rfm_atlas.web import FlaskApplicationFactory

app = FlaskApplicationFactory().create()
