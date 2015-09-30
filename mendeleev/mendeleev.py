# -*- coding: utf-8 -*-

#The MIT License (MIT)
#
#Copyright (c) 2015 Lukasz Mentel
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.

import os
import pandas as pd

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import sqlite

from .tables import (Base, Element, IonizationEnergy, IonicRadius,
        OxidationState, Isotope, Series)

__all__ = ['element', 'get_session', 'get_engine', 'get_table', 'ids_to_attr',
           'get_ips', 'deltaN']

def get_session():
    '''Return the database session connection.'''

    dbpath = os.path.join(os.path.abspath(os.path.dirname(__file__)), "elements.db")
    engine = create_engine("sqlite:///{path:s}".format(path=dbpath), echo=False)
    db_session =  sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return db_session()

def get_engine():
    '''Return the db engine'''

    dbpath = os.path.join(os.path.abspath(os.path.dirname(__file__)), "elements.db")
    engine = create_engine("sqlite:///{path:s}".format(path=dbpath), echo=False)
    return engine

def element(ids):
    '''
    Based on the type of the `ids` identifier return either an ``Element``
    object from the database, or a list of ``Element`` objects if the `ids` is
    a list or a tuple of identifiers. Valid identifiers for an element are:
    *name*, *symbol*, *atomic number*.
    '''

    if isinstance(ids, (list, tuple)):
        return [get_element(i) for i in ids]
    elif isinstance(ids, (str, int)):
        return get_element(ids)
    else:
        raise ValueError("Expected a <list>, <tuple>, <str> or <int>, got: {0:s}".format(type(ids)))

def get_element(ids):
    '''
    Return an element from the database based on the `ids` identifier passed.
    Valid identifiers for an element are: *name*, *symbol*, *atomic number*.
    '''

    session = get_session()

    if isinstance(ids, str):
        if len(ids) <= 3 and ids.lower() != "tin":
            return session.query(Element).filter(Element.symbol == ids).one()
        else:
            return session.query(Element).filter(Element.name == ids).one()
    elif isinstance(ids, int):
        return session.query(Element).filter(Element.atomic_number == ids).one()
    else:
        raise ValueError("Expecting a <str> or <int>, got: {0:s}".format(type(ids)))

def get_table(tablename,  **kwargs):
    '''
    Return a table from the database as pandas DataFrame

    Args:
      tablename: str
        Name of the table from the database
      kwargs:
        A dictionary of keyword arguments to pass to the `pandas.read_qsl`

    Returns:
      df: pandas.DataFrame
        Pandas DataFrame with the contents of the table
    '''

    tables = ['elements', 'isotopes', 'ionicradii', 'ionizationenergies',
              'groups', 'series', 'oxidationstates']

    if tablename in tables:
        engine = get_engine()
        df = pd.read_sql(tablename, engine, **kwargs)
        return df
    else:
        raise ValueError('Table should be one of: {}'.format(", ".join(tables)))

def ids_to_attr(ids, attr='atomic_number'):
    '''
    Convert the element ids: atomic numbers, symbols, element names or a
    combination of the above to a list of corresponding attributes.

    Args:
      ids: list, str or int
        A list of atomic number, symbols, element names of a combination of them
      attr: str
        Name of the desired attribute

    Returns:
      out: list
        List of attributes corresponding to the ids
    '''

    if isinstance(ids, (list, tuple)):
        return [getattr(e, attr) for e in element(ids)]
    else:
        return [getattr(element(ids), attr)]

def get_ips(ids=None, deg=1):
    '''
    Return a pandas DataFrame with ionization energies for a set of elements.

    Args:
      ids: list, str or int
        A list of atomic number, symbols, element names of a combination of the
        above. If nothing is specified all elements are selected.
      deg: int or list of int
        Degree of ionization, either as int or a list of ints. If a list is
        passed then the output will contain ionization energies corresponding
        to particalr degrees in columns.

    Returns:
      df: DataFrame
        Pandas DataFrame with atomic numbers, symbols and ionization energies
    '''

    session = get_session()
    engine = get_engine()

    if ids is None:
        atns = range(1, 119)
    else:
        atns = ids_to_attr(ids, attr='atomic_number')

    query = session.query(Element.atomic_number, Element.symbol).filter(Element.atomic_number.in_(atns))
    df = pd.read_sql_query(query.statement.compile(dialect=sqlite.dialect()), engine)

    if isinstance(deg, (list, tuple)):
        if all(isinstance(d, int) for d in deg):
            for d in deg:
                query = session.query(IonizationEnergy).\
                            filter(IonizationEnergy.degree == d).\
                            filter(IonizationEnergy.atomic_number.in_((atns)))
                out = pd.read_sql_query(query.statement.compile(dialect=sqlite.dialect()), engine)
                out = out[['atomic_number', 'energy']]
                out.columns = ['atomic_number', 'IP{0:d}'.format(d)]
                df = pd.merge(df, out, on='atomic_number', how='left')
        else:
            raise ValueError('deg should be a list of ints')
    elif isinstance(deg, int):
        query = session.query(IonizationEnergy).\
                    filter(IonizationEnergy.degree == deg).\
                    filter(IonizationEnergy.atomic_number.in_((atns)))
        out = pd.read_sql_query(query.statement.compile(dialect=sqlite.dialect()), engine)
        out = out[['atomic_number', 'energy']]
        out.columns = ['atomic_number', 'IP{0:d}'.format(deg)]
        df = pd.merge(df, out, on='atomic_number', how='left')
    else:
        raise ValueError('deg should be an int or a list or tuple of ints')

    return df

def get_ionic_radii(ids=None, charge=1, coord=None):
    '''
    Return a pandas DataFrame with ionic radii for a set of elements.

    Args:
      ids: list, str or int
        A list of atomic number, symbols, element names of a combination of the
        above. If nothing is specified all elements are selected.
      charge: int
        Charge of the ion for the ionic radii
      coord: str
        Coordination type for the ionic radii

    Returns:
      df: DataFrame
        Pandas DataFrame with atomic numbers, symbols and ionic radii
    '''

    session = get_session()
    engine = get_engine()

    if ids is None:
        atns = range(1, 119)
    else:
        atns = ids_to_attr(ids, attr='atomic_number')

    query = session.query(Element.atomic_number, Element.symbol).filter(Element.atomic_number.in_(atns))
    df = pd.read_sql_query(query.statement.compile(dialect=sqlite.dialect()), engine)

    if coord:
        query = session.query(IonicRadius).\
                            filter(IonicRadius.charge == charge).\
                            filter(IonicRadius.coordination == coord).\
                            filter(IonicRadius.atomic_number.in_(atns))
    else:
        query = session.query(IonicRadius).\
                            filter(IonicRadius.charge == charge).\
                            filter(IonicRadius.atomic_number.in_(atns))
    out = pd.read_sql_query(query.statement.compile(dialect=sqlite.dialect()), engine)
    df = pd.merge(df, out, on='atomic_number', how='left')

    return df

def deltaN(id1, id2, charge1=0, charge2=0):
    '''
    Calcualte the approximate number of transferred electrons between elements
    or ions `id1` and `id2` according to

    .. math::

       \Delta N = \frac{\chi_{A} - \chi_{B}}{2(\eta_{A} + \eta_{B})}

    '''

    session = get_session()
    atns = ids_to_attr([id1, id2], attr='atomic_number')


    e1, e2 = [session.query(Element).filter(Element.atomic_number == a).one() for a in atns]

    chi = [x.abselen(charge=c) for x, c in zip([e1, e2], [charge1, charge2])]

    if all(x is not None for x in chi):
        return (chi[0] - chi[1])/(2.0*(e1.hardness(charge=charge1) + e2.hardness(charge=charge2)))
    else:
        return None
