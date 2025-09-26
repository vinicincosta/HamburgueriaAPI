from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from werkzeug.security import generate_password_hash, check_password_hash

# Configuração do banco de dados
engine = create_engine('sqlite:///BancoRoyal.db', connect_args={"check_same_thread": False})
local_session = scoped_session(sessionmaker(bind=engine))

Base = declarative_base()


class Lanche(Base):
    __tablename__ = 'lanches'
    id_lanche = Column(Integer, primary_key=True)
    nome_lanche = Column(String(20), nullable=False, index=True)
    descricao_lanche = Column(String(255), index=True)
    valor_lanche = Column(Float, index=True)
    disponivel = Column(Boolean, default=True, index=True)

    def __repr__(self):
        return '<Lanche: {} {}>'.format(self.id_lanche, self.nome_lanche)

    def save(self, db_session):
        try:
            db_session.add(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def delete(self, db_session):
        try:
            db_session.delete(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def serialize(self):
        var_lanche = {
            'id_lanche': self.id_lanche,
            'nome_lanche': self.nome_lanche,
            'descricao_lanche': self.descricao_lanche,
            'disponivel': self.disponivel,
            'valor_lanche': self.valor_lanche,
        }
        return var_lanche

class Insumo(Base):
    __tablename__ = 'insumos'
    id_insumo = Column(Integer, primary_key=True)
    nome_insumo = Column(String(20), nullable=False, index=True)
    qtd_insumo = Column(Integer, default=0, nullable=False, index=True)
    categoria_id = Column(Integer, ForeignKey('categorias.id_categoria'), nullable=False)

    def __repr__(self):
        return '<Insumo: {} {}>'.format(self.id_insumo, self.nome_insumo)

    def save(self, db_session):
        try:
            db_session.add(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def delete(self, db_session):
        try:
            db_session.delete(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def serialize(self):
        var_insumo = {
            'id_insumo': self.id_insumo,
            'nome_insumo': self.nome_insumo,
            'qtd_insumo': self.qtd_insumo,
            'categoria_id': self.categoria_id,
        }
        return var_insumo

class Lanche_insumo(Base):
    __tablename__ = 'lanche_insumos'
    id_lanche_insumo = Column(Integer, primary_key=True)
    qtd_insumo = Column(Integer, index=True)
    lanche_id = Column(Integer, ForeignKey('lanches.id_lanche'))
    insumo_id = Column(Integer, ForeignKey('insumos.id_insumo'))

    def __repr__(self):
        return '<Lanche_insumo: {} {}>'.format(self.id_lanche_insumo, self.qtd_insumo)

    def save(self, db_session):
        try:
            db_session.add(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def delete(self, db_session):
        try:
            db_session.delete(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def serialize(self):
        var_lanche_insumo = {
            'id_lanche_insumo': self.id_lanche_insumo,
            'qtd_insumo': self.qtd_insumo,
            'lanche_id': self.lanche_id,
            'insumo_id': self.insumo_id,
        }
        return var_lanche_insumo

class Categoria(Base):
    __tablename__ = 'categorias'
    id_categoria = Column(Integer, primary_key=True)
    nome_categoria = Column(String(20), nullable=False, index=True)

    def __repr__(self):
        return '<Categoria: {} {}>'.format(self.id_categoria, self.nome_categoria)

    def save(self, db_session):
        try:
            db_session.add(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def delete(self, db_session):
        try:
            db_session.delete(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def serialize(self):
        var_categoria = {
            'id_categoria': self.id_categoria,
            'nome_categoria': self.nome_categoria,
        }
        return var_categoria

class Venda(Base):
    __tablename__ = 'vendas'
    id_venda = Column(Integer, primary_key=True)
    data_venda = Column(String(10), nullable=False, index=True)
    valor_venda = Column(Float, nullable=False, index=True)
    status_venda = Column(Boolean, default=True, index=True)
    detalhamento = Column(String(50), nullable=False, index=True)
    ajustes_receita = Column(String(100), nullable=False, index=True)
    endereco = Column(String, nullable=False)
    forma_pagamento = Column(String, nullable=False)

    # relacionamento com Lanche
    lanche_id = Column(Integer, ForeignKey('lanches.id_lanche'), nullable=False)
    # relacionamento com Pessoa
    pessoa_id = Column(Integer, ForeignKey('pessoas.id_pessoa'), nullable=False)

    def __repr__(self):
        return '<Venda: {} {}>'.format(self.id_venda, self.data_venda)

    def save(self, db_session):
        try:
            db_session.add(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def delete(self, db_session):
        try:
            db_session.delete(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def serialize(self):
        var_venda = {
            "id_venda": self.id_venda,
            "data_venda": self.data_venda,
            "valor_venda": self.valor_venda,
            "status_venda": self.status_venda,
            "detalhamento": self.detalhamento,
            "ajustes_receita": self.ajustes_receita,
            "lanche_id": self.lanche_id,
            "pessoa_id": self.pessoa_id,
            "forma_pagamento": self.forma_pagamento,
            "endereco": self.endereco,
        }
        return var_venda

class Entrada(Base):
    __tablename__ = 'entradas'
    id_entrada = Column(Integer, primary_key=True)
    nota_fiscal = Column(String(20), index=True)
    data_entrada = Column(String(10), nullable=False, index=True)
    qtd_entrada = Column(Integer, nullable=False, index=True)
    valor_entrada = Column(Float, nullable=False, index=True)


    # relacionamento com Insumo
    insumo_id = Column(Integer, ForeignKey('insumos.id_insumo'), nullable=False)

    def __repr__(self):
        return f'<Entrada: {self.id_entrada} {self.data_entrada}>'

    def save(self, db_session):
        try:
            db_session.add(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def delete(self, db_session):
        try:
            db_session.delete(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def serialize(self):
        return {
            'id_entrada': self.id_entrada,
            'nota_fiscal': self.nota_fiscal,
            'data_entrada': self.data_entrada,
            'qtd_entrada': self.qtd_entrada,
            'valor_entrada': self.valor_entrada,
            'insumo_id': self.insumo_id
        }

class Pessoa(Base):
    __tablename__ = 'pessoas'
    id_pessoa = Column(Integer, primary_key=True)
    nome_pessoa = Column(String(20), nullable=False, index=True)
    cpf = Column(String(11), nullable=True, index=True)
    salario = Column(Float, nullable=True, index=True)
    papel = Column(String(20), nullable=True, index=True)
    status_pessoa = Column(String, nullable=True)
    senha_hash = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)


    def __repr__(self):
        return 'Pessoa: {} {}>'.format(self.id_pessoa, self.nome_pessoa)

    def set_senha_hash(self, senha):
        self.senha_hash = generate_password_hash(senha)


    def check_password_hash(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def save(self, db_session):
        try:
            db_session.add(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def delete(self, db_session):
        try:
            db_session.delete(self)
            db_session.commit()
        except:
            db_session.rollback()
            raise

    def serialize(self):
        var_pessoa = {
            'id_pessoa': self.id_pessoa,
            'nome_pessoa': self.nome_pessoa,
            'cpf': self.cpf,
            'salario': self.salario,
            'papel': self.papel,
            'status_pessoa': self.status_pessoa,
            'email': self.email,

        }
        return var_pessoa

def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == '__main__':
    init_db()