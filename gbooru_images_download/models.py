#!/usr/bin/env python3
"""Model module."""
from datetime import datetime
import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy.types import TIMESTAMP
from sqlalchemy_utils.types import URLType, JSONType, ChoiceType
import structlog


log = structlog.getLogger(__name__)
db = SQLAlchemy()

url_tags = db.Table(
    'url_tags',
    db.Column('url_id', db.Integer, db.ForeignKey('url.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True))
search_image_match_results = db.Table(
    'search_image_match_results',
    db.Column('search_image_page_id', db.Integer, db.ForeignKey('search_image_page.id'), primary_key=True),   # NOQA
    db.Column('match_result_id', db.Integer, db.ForeignKey('match_result.id'), primary_key=True))
search_query_match_results = db.Table(
    'search_query_match_results',
    db.Column('search_query_id', db.Integer, db.ForeignKey('search_query.id'), primary_key=True),
    db.Column('match_result_id', db.Integer, db.ForeignKey('match_result.id'), primary_key=True))
match_result_json_data = db.Table(
    'match_result_json_data',
    db.Column('match_result_id', db.Integer, db.ForeignKey('match_result.id'), primary_key=True),
    db.Column('json_data_id', db.Integer, db.ForeignKey('json_data.id'), primary_key=True))


class Base(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(TIMESTAMP, default=datetime.now, nullable=False)


class SingleStringModel(Base):
    __abstract__ = True
    value = db.Column(db.String)


class Url(Base):
    value = db.Column(URLType, unique=True, nullable=False)
    tags = db.relationship(
        'Tag', secondary=url_tags, lazy='subquery',
        backref=db.backref('urls', lazy=True))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)

    def get_sorted_tags(self):
        nnm_t, nm_t = [], []
        for tag in self.tags:
            (nnm_t, nm_t)[bool(tag.namespace)].append(tag)
        res = sorted(nm_t, key=lambda x: x.namespace.value)
        res.extend(sorted(nnm_t, key=lambda x: x.value))
        return res

    def filename(self):
        url = str(self.value)
        if self.value.host == 'images-blogger-opensocial.googleusercontent.com' \
                and str(self.value.path) == '/gadgets/proxy' \
                and 'url' in self.value.query.params:
            url = self.value.query.params['url']
        return os.path.splitext(os.path.basename(url))[0]


class SearchTerm(SingleStringModel):
    url_id = db.Column(db.Integer, db.ForeignKey('url.id'))
    url = db.relationship(
        'Url', lazy='subquery',
        backref=db.backref('search_term', lazy=True))

    def __repr__(self):
        templ = '<SearchTerm:{0.id} {0.value}>'
        return templ.format(self)


class SearchQuery(Base):
    """Search query."""
    search_term_id = db.Column(db.Integer, db.ForeignKey('search_term.id'))
    search_term = db.relationship(
        'SearchTerm', lazy='subquery',
        backref=db.backref('search_queries', lazy=True))
    page = db.Column(db.Integer)
    match_results = db.relationship(
        'MatchResult', secondary=search_query_match_results, lazy='subquery',
        backref=db.backref('search_queries', lazy=True))

    def __repr__(self):
        templ = '<SearchQuery:{0.id} q:[{0.search_term.value}] p:{0.page}>'
        return templ.format(self)

    def to_dict(self):
        """Get dict from model."""

        def get_dict_from_tags(url_obj):
            res = []
            if url_obj.tags:
                for tag in url_obj.tags:
                    res.append((tag.namespace.value, tag.value))
            return res

        match_results = []
        for item in self.match_results:
            match_results.append({
                'img_url': {
                    'value': str(item.img_url.value),
                    'tags': get_dict_from_tags(item.img_url),
                },
                'thumbnail_url': {
                    'value': str(item.thumbnail_url.value),
                    'tags': get_dict_from_tags(item.thumbnail_url),
                },
            })
        return {
            'page': self.page,
            'search_term': self.search_term.value,
            'match_result': match_results,
        }


class MatchResult(Base):
    """Match result."""
    json_data = db.relationship(
        'JsonData', secondary=match_result_json_data, lazy='subquery',
        backref=db.backref('match_results', lazy=True))
    # image and thumbnail
    img_url_id = db.Column(db.Integer, db.ForeignKey('url.id'))
    img_url = db.relationship(
        'Url', foreign_keys='MatchResult.img_url_id', lazy='subquery',
        backref=db.backref('match_results', lazy=True, cascade='delete'))
    thumbnail_url_id = db.Column(db.Integer, db.ForeignKey('url.id'))
    thumbnail_url = relationship(
        'Url', foreign_keys='MatchResult.thumbnail_url_id', lazy='subquery',
        backref=db.backref('thumbnail_match_results', lazy=True, cascade='delete'))


class JsonData(Base):
    value = db.Column(JSONType)


class FilteredImageUrl(Base):
    img_url_id = db.Column(db.Integer, db.ForeignKey('url.id'), unique=True)
    img_url = db.relationship(
        'Url', foreign_keys='FilteredImageUrl.img_url_id', lazy='subquery',
        backref=db.backref('filtered', lazy=True, cascade='delete'))


class Namespace(SingleStringModel):
    """Namespace model."""

    def __repr__(self):
        return '<Namespace:{0.id} {0.value}>'.format(self)


class HiddenNamespace(Base):
    namespace_id = db.Column(db.Integer, db.ForeignKey('namespace.id'), unique=True)
    namespace = db.relationship(
        'Namespace', foreign_keys='HiddenNamespace.namespace_id', lazy='subquery',
        backref=db.backref('hidden', lazy=True, cascade='delete'))


class NamespaceHtmlClass(Base):
    value = db.Column(db.String)
    namespace_id = db.Column(db.Integer, db.ForeignKey('namespace.id'))
    namespace = db.relationship(
        'Namespace', foreign_keys='NamespaceHtmlClass.namespace_id', lazy='subquery',
        backref=db.backref('html_class', lazy=True, cascade='delete'))


class Tag(SingleStringModel):
    """Tag model."""
    namespace_id = db.Column(db.Integer, db.ForeignKey('namespace.id'))
    namespace = db.relationship(
        'Namespace', foreign_keys='Tag.namespace_id', lazy='subquery',
        backref=db.backref('tags', lazy=True, cascade='delete'))

    @property
    def as_string(self):
        nm = '{}:'.format(self.namespace.value) if self.namespace else ''
        return ''.join([nm, self.value])

    def get_html_class(self):
        if not self.namespace:
            return
        val = 'tag-' + self.namespace.value
        val = val.replace(' ', '-')
        if self.namespace.html_class:
            return val + ' ' + ' '.join([x.value for x in self.html_class])
        return val

    def __repr__(self):
        templ = '<Tag:{0.id} {0.as_string}>'
        return templ.format(self)


class HiddenTag(Base):
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), unique=True)
    tag = db.relationship(
        'Tag', foreign_keys='HiddenTag.tag_id', lazy='subquery',
        backref=db.backref('hidden', lazy=True, cascade='delete'))


class SearchImage(Base):
    """Search image"""
    img_checksum = db.Column(db.String)
    img_url_id = db.Column(db.Integer, db.ForeignKey('url.id'))
    img_url = db.relationship(
        'Url', lazy='subquery',
        backref=db.backref('search_image', lazy=True))
    # url result
    search_url = db.Column(URLType)
    similar_search_url = db.Column(URLType)
    size_search_url = db.Column(URLType)
    # img guess
    img_guess = db.Column(db.String)


class TextMatch(Base):
    # mostly on every text match obj
    title = db.Column(db.String)
    url = db.Column(URLType)
    url_text = db.Column(db.String)
    text = db.Column(db.String)
    # optional, it also mean there is thumbnail
    imgres_url = db.Column(URLType)
    imgref_url = db.Column(URLType)
    # search image
    search_image_id = db.Column(db.Integer, db.ForeignKey('search_image.id'))
    search_image_model = relationship(
        'SearchImage', foreign_keys='TextMatch.search_image_id', lazy='subquery',
        backref=db.backref('text_matches', lazy=True))
    # image (optional)
    img_id = db.Column(db.Integer, db.ForeignKey('match_result.id'))
    img = db.relationship(
        'MatchResult', foreign_keys='TextMatch.img_id', lazy='subquery',
        backref=db.backref('text_matches', lazy=True))


class MainSimilarResult(Base):
    title = db.Column(db.String)
    search_url = db.Column(URLType)
    search_image_id = db.Column(db.Integer, db.ForeignKey('search_image.id'))
    search_image_model = relationship(
        'SearchImage', foreign_keys='MainSimilarResult.search_image_id', lazy='subquery',
        backref=db.backref('main_similar_results', lazy=True))


class SearchImagePage(Base):
    TYPE_SIMILAR = '1'
    TYPE_SIZE = '2'
    TYPES = [
        (TYPE_SIMILAR, 'Similar'),
        (TYPE_SIZE, 'Size'),
    ]
    page = db.Column(db.Integer, default=1, nullable=False)
    search_type = db.Column(ChoiceType(TYPES))
    search_img_id = db.Column(db.Integer, db.ForeignKey('search_image.id'))
    search_img = db.relationship(
        'SearchImage', foreign_keys='SearchImagePage.search_img_id', lazy='subquery',
        backref=db.backref('pages', lazy=True))
    match_results = db.relationship(
        'MatchResult', secondary=search_image_match_results, lazy='subquery',
        backref=db.backref('search_image_pages', lazy=True))


def get_or_create(session, model, **kwargs):
    """Creates an object or returns the object if exists."""
    instance = session.query(model).filter_by(**kwargs).first()
    created = False
    if not instance:
        instance = model(**kwargs)
        session.add(instance)
        created = True
    return instance, created
