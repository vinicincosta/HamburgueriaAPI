import json
from flask import Flask, jsonify, request, redirect, url_for
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from datetime import datetime
from collections import defaultdict
from werkzeug.exceptions import BadRequest
from models import *
from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt_identity, get_jwt
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
# from flask_login import LoginManager, current_user, login_required, login_user, logout_user, current_user
from sqlalchemy import func, and_, not_

app = Flask(__name__)
CORS(app)
app.config['JWT_SECRET_KEY'] = "03050710"
jwt = JWTManager(app)


def roles_required(*roles):
    """
        Decorator: roles_required(roles...)
        ----------------------------------------------------
        Restringe o acesso da rota aos papéis (roles) informados.

         Como funciona:
            - Lê o JWT atual
            - Busca o usuário pelo email (identity)
            - Verifica se o papel do usuário está na lista de roles permitidos
            - Caso positivo → permite o acesso
            - Caso negativo → retorna 403

         Exemplo de uso:
            @app.route('/admin')
            @jwt_required()
            @roles_required('admin', 'gerente')
            def rota_admin():
                return "Somente admins"
        """

    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            current_user = get_jwt_identity()
            db = local_session()
            try:
                sql = select(Pessoa).where(Pessoa.email == current_user)
                user = db.execute(sql).scalar()
                if user and user.papel in roles:
                    return fn(*args, **kwargs)
                return jsonify(msg="Acesso negado: privilégios insuficientes"), 403
            finally:
                db.close()

        return decorated

    return wrapper


@app.route('/login', methods=['POST'])
def login():
    """
        POST /login
        ----------------------------------------------------
        Realiza login do usuário e retorna:
        - token de acesso (JWT)
        - papel do usuário
        - nome do usuário

         Corpo da requisição:
        {
            "email": "usuario@email.com",
            "senha": "123456"
        }

         Exemplo de resposta:
        {
            "access_token": "<TOKEN_JWT>",
            "papel": "admin",
            "nome": "João Silva"
        }
        """
    dados = request.get_json()
    email = dados.get('email')
    senha = dados.get('senha')

    db_session = local_session()

    try:
        # Verifica se email e senha foram fornecidos
        if not email or not senha:
            return jsonify({'msg': 'Email e senha são obrigatórios'}), 400

        # Consulta o usuário pelo CPF
        sql = select(Pessoa).where(Pessoa.email == email)
        user = db_session.execute(sql).scalar()

        # Verifica se o usuário existe e se a senha está correta
        if user and user.check_password_hash(senha):
            access_token = create_access_token(
                identity=email,
                additional_claims={
                    "id_usuario": user.id_pessoa,
                    "papel": user.papel
                }
            )
            papel = user.papel  # Obtém o papel do usuário
            nome = user.nome_pessoa  # Obtém o nome do usuário
            print(f"Login bem-sucedido: {nome}, Papel: {papel}")  # Diagnóstico
            # login_user(user)
            return jsonify(access_token=access_token, papel=papel, nome=nome)  # Retorna o nome também
        print("Credenciais inválidas.")  # Diagnóstico
        return jsonify({'msg': 'Credenciais inválidas'}), 401
    finally:
        db_session.close()


@app.route('/cadastro_pessoas_login', methods=['POST'])
# @jwt_required()
# @roles_required('admin')
def cadastro():
    """
        POST /cadastro_pessoas_login
        ----------------------------------------------------
        Cadastra um novo usuário no sistema.
        Se papel não for informado, assume "cliente".
        CPF somente é usado se papel = "admin".

         Corpo da requisição:
        {
            "nome_pessoa": "Maria",
            "cpf": "12345678901",
            "email": "maria@gmail.com",
            "papel": "admin",
            "senha": "123456",
            "salario": 2500
        }

         Exemplo de resposta:
        {
            "msg": "Usuário criado com sucesso",
            "user_id": 7
        }
        """
    dados = request.get_json()
    nome_pessoa = dados['nome_pessoa']
    cpf = dados['cpf']
    email = dados['email']
    papel = dados.get('papel', 'cliente')  # padrão vira cliente
    senha = dados['senha']
    salario = dados['salario']

    # 🔹 Sempre força status como "Ativo"
    status_pessoa = "Ativo"

    if not nome_pessoa or not email or not senha:
        return jsonify({"msg": "Nome, Email e senha são obrigatórios"}), 400

    # 🔹 Se o papel for admin → valida CPF
    if papel == "admin":
        if not cpf or len(cpf) != 11 or not cpf.isdigit():
            return jsonify({"msg": "O CPF do admin deve conter exatamente 11 dígitos numéricos."}), 400
    else:
        # 🔹 Se não for admin → ignora CPF e zera para evitar lixo
        cpf = None

    db_session = local_session()
    try:
        # Verificar se o usuário já existe
        user_check = select(Pessoa).where(Pessoa.email == email)
        usuario_existente = db_session.execute(user_check).scalar()

        if usuario_existente:
            return jsonify({"msg": "Usuário já existe"}), 400

        novo_usuario = Pessoa(
            nome_pessoa=nome_pessoa,
            cpf=cpf,
            papel=papel,
            salario=salario,
            status_pessoa=status_pessoa,  # sempre "Ativo"
            email=email
        )
        novo_usuario.set_senha_hash(senha)
        db_session.add(novo_usuario)
        db_session.commit()

        user_id = novo_usuario.id_pessoa
        return jsonify({"msg": "Usuário criado com sucesso", "user_id": user_id}), 201

    except Exception as e:
        db_session.rollback()
        return jsonify({"msg": f"Erro ao registrar usuário: {str(e)}"}), 500
    finally:
        db_session.close()


@app.route('/update_insumo/<int:id_insumo>', methods=['PUT'])
def update_insumo(id_insumo):
    """
        PUT /update_insumo/<id_insumo>
        ----------------------------------------------------
        Atualiza os dados de um insumo existente.
        Apenas os campos enviados no JSON são modificados.

         Parâmetro:
            id_insumo (int) — ID do insumo a ser atualizado.

         Corpo da requisição (opcional):
        {
            "nome_insumo": "Queijo Mussarela",
            "qtd_insumo": 12,
            "custo": 5.80,
            "categoria_id": 1
        }

         Regras automáticas:
            - Se quantidade <= 5 → todos os lanches que usam esse insumo serão desativados.

         Exemplo de resposta:
        {
            "success": true,
            "message": "Insumo atualizado com sucesso.",
            "insumo": {
                "id_insumo": 3,
                "nome_insumo": "Queijo Mussarela",
                "qtd_insumo": 12,
                "categoria_id": 1
            }
        }
        """

    db_session = local_session()
    try:
        # Se não houver JSON, define um dicionário vazio
        data = request.get_json(silent=True) or {}

        insumo = db_session.execute(
            select(Insumo).filter_by(id_insumo=id_insumo)
        ).scalar_one_or_none()

        if not insumo:
            return jsonify({"error": "Insumo não encontrado"}), 404

        # Atualiza os dados apenas se vierem no JSON, senão mantém os atuais
        insumo.nome_insumo = data.get('nome_insumo', insumo.nome_insumo)
        insumo.qtd_insumo = data.get('qtd_insumo', insumo.qtd_insumo)
        insumo.custo = data.get('custo', insumo.custo)
        insumo.categoria_id = data.get('categoria_id', insumo.categoria_id)

        LIMITE_MINIMO = 5
        if insumo.qtd_insumo <= LIMITE_MINIMO:
            # pega todos os lanches que usam esse insumo
            lanches_relacionados = db_session.execute(select(Lanche)
                                                      .join(Lanche_insumo, Lanche.id_lanche == Lanche_insumo.lanche_id)
                                                      .filter(Lanche_insumo.insumo_id == insumo.id_insumo)).all()

            # desativa os lanches
            for lanche in lanches_relacionados:
                lanche.disponivel = False

        db_session.commit()
        return jsonify({
            "success": True,
            "message": "Insumo atualizado com sucesso.",
            "insumo": insumo.serialize()
        }), 200

    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db_session.close()


@app.route('/update_bebida/<int:id_bebida>', methods=['PUT'])
def update_bebida(id_bebida):
    """
        PUT /update_bebida/<id_bebida>
        ----------------------------------------------------
        Atualiza os dados de uma bebida.
        Apenas os campos enviados no JSON serão modificados.

         Parâmetro:
            id_bebida (int)

         Corpo da requisição (opcional):
        {
            "nome_bebida": "Guaraná",
            "descricao": "350ml",
            "valor": 6.50,
            "quantidade": 20,
            "categoria": "Refrigerante"
        }

        Regra automática:
            - Se quantidade > 5 → status_bebida = True
            - Caso contrário → status_bebida = False

        Exemplo de resposta:
        {
            "success": true,
            "message": "Bebida atualizada com sucesso.",
            "bebida": {
                "id_bebida": 4,
                "nome_bebida": "Guaraná",
                "quantidade": 20
            }
        }
        """
    db_session = local_session()
    try:
        data = request.get_json(silent=True) or {}

        bebida = db_session.execute(
            select(Bebida).filter_by(id_bebida=id_bebida)
        ).scalar_one_or_none()

        if not bebida:
            return jsonify({"error": "Bebida não encontrada"}), 404

        # Atualiza apenas os campos enviados
        bebida.nome_bebida = data.get('nome_bebida', bebida.nome_bebida)
        bebida.descricao = data.get('descricao', bebida.descricao)
        bebida.valor = data.get('valor', bebida.valor)
        bebida.quantidade = data.get('quantidade', bebida.quantidade)
        bebida.categoria = data.get('categoria', bebida.categoria)

        # Define limite mínimo
        LIMITE_MINIMO = 5
        bebida.status_bebida = bebida.quantidade > LIMITE_MINIMO

        db_session.commit()

        return jsonify({
            "success": True,
            "message": "Bebida atualizada com sucesso.",
            "bebida": bebida.serialize()
        }), 200

    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db_session.close()


# Cadastro (POST)
@app.route('/usuarios', methods=['POST'])
def cadastro_usuarios():
    """
        API para cadastrar novos usuários no sistema.

        # Endpoint:
        POST /usuarios

        ## Corpo da Requisição (JSON)
        {
            "nome_pessoa": "Carlos Souza",
            "email": "carlos@email.com",
            "papel": "cliente",
            "senha": "123456",
            "cpf": "00011122233"
        }

        ## Resposta (JSON)
        {
            "msg": "Usuário criado com sucesso",
            "user_id": 12
        }
        """
    dados = request.get_json()
    nome_pessoa = dados['nome_pessoa']
    email = dados['email']
    papel = dados.get('papel', 'cliente')
    senha = dados['senha']
    cpf = dados['cpf']
    # salario = dados['salario']

    if not nome_pessoa or not email or not senha:
        return jsonify({"msg": "Nome de usuário, email e senha são obrigatórios"}), 400

    banco = local_session()
    try:
        # Verificar se o usuário já existe
        user_check = select(Pessoa).where(Pessoa.nome_pessoa == nome_pessoa)
        usuario_existente = banco.execute(user_check).scalar()

        if usuario_existente:
            return jsonify({"msg": "Usuário já existe"}), 400

        novo_usuario = Pessoa(nome_pessoa=nome_pessoa, email=email, papel=papel)
        novo_usuario.set_senha_hash(senha)
        banco.add(novo_usuario)
        banco.commit()

        user_id = novo_usuario.id_pessoa
        return jsonify({"msg": "Usuário criado com sucesso", "user_id": user_id}), 201
    except Exception as e:
        banco.rollback()
        return jsonify({"msg": f"Erro ao registrar usuário: {str(e)}"}), 500
    finally:
        banco.close()


@app.route('/lanches', methods=['POST'])
# @jwt_required()
# @roles_required('cliente', 'garcom', 'cozinha','admin')
def cadastrar_lanche():
    """
       API para cadastrar um novo lanche.

       # Endpoint:
       POST /lanches

       ## Corpo da Requisição (JSON)
       {
           "nome_lanche": "X-Burguer",
           "descricao_lanche": "Pão, carne, queijo",
           "valor_lanche": 25.90
       }

       ## Resposta (JSON)
       {
           "success": "Cadastrado com sucesso",
           "lanches": { ... }
       }
       """
    db_session = local_session()
    try:
        dados_lanche = request.get_json()

        campos_obrigatorios = ["nome_lanche", "descricao_lanche", "valor_lanche"]

        if not all(campo in dados_lanche for campo in campos_obrigatorios):
            return jsonify({"error": "Campo inexistente"}), 400

        if any(not dados_lanche[campo] for campo in campos_obrigatorios):
            return jsonify({"error": "Preencher todos os campos"}), 400

        else:
            nome_lanche = dados_lanche['nome_lanche']
            descricao_lanche = dados_lanche['descricao_lanche']
            valor_lanche = dados_lanche['valor_lanche']
            form_novo_lanche = Lanche(
                nome_lanche=nome_lanche,
                descricao_lanche=descricao_lanche,
                valor_lanche=valor_lanche
            )
            print(form_novo_lanche)
            form_novo_lanche.save(db_session)
            dicio = form_novo_lanche.serialize()
            resultado = {"success": "Cadastrado com sucesso", "lanches": dicio}

            return jsonify(resultado), 201

    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route("/entradas", methods=["POST"])
# @jwt_required()
# @roles_required('admin')
def cadastrar_entrada():
    """
        API para registrar entrada de estoque de insumos ou bebidas.

        # Endpoint:
        POST /entradas

        ## Corpo da Requisição (JSON)
        {
            "qtd_entrada": 10,
            "data_entrada": "2025-03-20",
            "nota_fiscal": "NF123",
            "valor_entrada": 150.0,
            "insumo_id": 2
        }

        ## Resposta (JSON)
        {
            "success": "Entrada cadastrada com sucesso",
            "entrada": { ... }
        }
        """
    db_session = local_session()
    try:
        dados = request.get_json()

        # Campos obrigatórios
        campos_obrigatorios = ["qtd_entrada", "data_entrada", "nota_fiscal", "valor_entrada"]

        if not all(campo in dados for campo in campos_obrigatorios):
            return jsonify({"error": "Campos obrigatórios ausentes"}), 400

        if any(dados[campo] == "" for campo in campos_obrigatorios):
            return jsonify({"error": "Preencha todos os campos"}), 400

            # Validações numéricas

        qtd = int(dados["qtd_entrada"])
        valor = float(dados["valor_entrada"])

        insumo_id = None
        bebida_id = None

        if qtd <= 0 or valor <= 0:
            return jsonify({"error": "Quantidade e valor devem ser maiores que zero"}), 400

        if 'insumo_id' in dados and 'bebida_id' in dados:
            return jsonify({"error": "Insira apenas o ID de um item"}), 400
        elif 'insumo_id' in dados:
            # Verificar se o insumo existe
            # insumo = local_session.query(Insumo).filter_by(id_insumo=dados["insumo_id"]).first()
            insumo = db_session.execute(select(Insumo).filter_by(id_insumo=dados["insumo_id"])).scalar()
            if not insumo:
                return jsonify({"error": "Não encontrado"}), 400
            insumo_id = dados['insumo_id']
            # Atualiza o estoque do insumo
            print("quantidade: ", insumo.qtd_insumo)
            insumo.qtd_insumo += qtd

            insumo.save(db_session)

        elif 'bebida_id' in dados:
            # bebida = local_session.query(Bebida).filter_by(id_bebida=dados["bebida_id"]).first()
            bebida = db_session.execute(select(Bebida).filter_by(id_bebida=dados["bebida_id"])).scalar_one_or_none()
            if not bebida:
                return jsonify({"error": "Não encontrado"}), 400
            bebida_id = dados['bebida_id']
            bebida.quantidade += qtd

            bebida.save(db_session)
        else:
            return jsonify({"error": "Não encontrado"}), 400

        # Cria a entrada
        nova_entrada = Entrada(
            nota_fiscal=dados["nota_fiscal"],
            data_entrada=dados["data_entrada"],
            qtd_entrada=qtd,
            valor_entrada=valor,
            insumo_id=insumo_id,
            bebida_id=bebida_id
        )

        nova_entrada.save(db_session)

        return jsonify({
            "success": "Entrada cadastrada com sucesso",
            "entrada": nova_entrada.serialize()
        }), 201

    except Exception as e:
        return jsonify({"error": f"Erro ao salvar entrada: {str(e)}"}), 500


@app.route("/bebidas", methods=["POST"])
def cadastrar_bebida():
    db_session = local_session()
    try:
        dados = request.get_json()
        print("DADOS RECEBIDOS:", dados)

        if not dados:
            return jsonify({"error": "JSON inválido"}), 400

        campos_obrigatorios = ["nome_bebida", "valor", "id_categoria"]
        faltando = [c for c in campos_obrigatorios if c not in dados]

        if faltando:
            return jsonify({
                "error": "Campos obrigatórios ausentes",
                "faltando": faltando
            }), 400

        nome_bebida = dados["nome_bebida"]
        descricao = dados.get("descricao")
        id_categoria = int(dados["id_categoria"])
        valor = float(dados["valor"])
        quantidade = 0

        nova_bebida = Bebida(
            nome_bebida=nome_bebida,
            descricao=descricao,
            categoria=id_categoria,
            valor=valor,
            quantidade=quantidade
        )

        nova_bebida.save(db_session)

        return jsonify({
            "success": "Cadastrado com sucesso",
            "bebida": nova_bebida.serialize()
        }), 201

    except Exception as e:
        print("ERRO API:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        db_session.close()



@app.route('/pedidos', methods=['POST'])
def cadastrar_pedido():

    db_session = local_session()

    try:
        dados = request.get_json()

        if not dados:
            return jsonify({"error": "JSON inválido"}), 400

        # -------- CAMPOS OBRIGATÓRIOS --------
        campos_obrigatorios = ["numero_mesa", "id_pessoa"]

        for campo in campos_obrigatorios:
            if campo not in dados or dados[campo] in [None, ""]:
                return jsonify({"error": f"Campo obrigatório ausente: {campo}"}), 400

        # -------- TRATA MESA OU DELIVERY --------
        numero_mesa_raw = dados.get("numero_mesa")

        if isinstance(numero_mesa_raw, str) and numero_mesa_raw.strip().lower() == "delivery":
            numero_mesa = 0
            tipo_pedido = "Delivery"
        else:
            try:
                numero_mesa = int(numero_mesa_raw)
                tipo_pedido = f"Mesa {numero_mesa}"
            except (ValueError, TypeError):
                return jsonify({"error": f"Número de mesa inválido: {numero_mesa_raw}"}), 400

        # -------- DADOS BÁSICOS --------
        id_pessoa = int(dados["id_pessoa"])
        qtd_lanche = int(dados.get("qtd_lanche", 1))
        data_pedido = dados.get("data_pedido", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        detalhamento = dados.get("detalhamento", "")

        # 🔥 Blindagem observacoes
        observacoes = dados.get("observacoes") or {"adicionar": [], "remover": []}

        id_lanche_raw = dados.get("id_lanche")
        id_bebida_raw = dados.get("id_bebida")

        id_lanche = int(id_lanche_raw) if id_lanche_raw not in [None, "", 0] else None
        id_bebida = int(id_bebida_raw) if id_bebida_raw not in [None, "", 0] else None

        if not id_lanche and not id_bebida:
            return jsonify({"error": "É necessário informar pelo menos um lanche ou uma bebida"}), 400

        receita_final = {}

        # -------- PROCESSAMENTO DO LANCHE --------
        if id_lanche:

            lanche = db_session.execute(
                select(Lanche).filter_by(id_lanche=id_lanche)
            ).scalar_one_or_none()

            if not lanche:
                return jsonify({"error": "Lanche não encontrado"}), 404

            receita = db_session.execute(
                select(Lanche_insumo).filter_by(lanche_id=id_lanche)
            ).scalars().all()

            if not receita:
                return jsonify({"error": "Esse lanche não tem receita cadastrada"}), 400

            receita_final = {
                item.insumo_id: item.qtd_insumo for item in receita
            }

            # -------- AJUSTES --------
            for rem in observacoes.get("remover", []):
                insumo_id = rem.get("insumo_id")
                qtd = rem.get("qtd", 0)

                if insumo_id is None:
                    continue

                insumo_id = int(insumo_id)

                if insumo_id in receita_final:
                    receita_final[insumo_id] = max(
                        0, receita_final[insumo_id] - qtd * 100
                    )

            for add in observacoes.get("adicionar", []):
                insumo_id = add.get("insumo_id")
                qtd = add.get("qtd", 0)

                if insumo_id is None:
                    continue

                insumo_id = int(insumo_id)

                receita_final[insumo_id] = receita_final.get(insumo_id, 0) + qtd * 100

            # -------- VERIFICA ESTOQUE --------
            for insumo_id, qtd in receita_final.items():

                insumo = db_session.execute(
                    select(Insumo).filter_by(id_insumo=insumo_id)
                ).scalar_one_or_none()

                if not insumo:
                    return jsonify({"error": f"Insumo ID {insumo_id} não encontrado"}), 404

                if insumo.qtd_insumo < qtd * qtd_lanche:
                    return jsonify({"error": f"Estoque insuficiente para: {insumo.nome_insumo}"}), 400

            # -------- BAIXA ESTOQUE --------
            for insumo_id, qtd in receita_final.items():

                insumo = db_session.execute(
                    select(Insumo).filter_by(id_insumo=insumo_id)
                ).scalar_one()

                insumo.qtd_insumo -= qtd * qtd_lanche
                db_session.add(insumo)

        # -------- BEBIDA --------
        if id_bebida:

            bebida = db_session.execute(
                select(Bebida).filter_by(id_bebida=id_bebida)
            ).scalar_one_or_none()

            if not bebida:
                return jsonify({"error": "Bebida não encontrada"}), 404

        receita_final_str_keys = {
            str(k): v for k, v in receita_final.items()
        }

        # -------- CRIAR PEDIDOS --------
        pedidos_registrados = []

        for _ in range(qtd_lanche):

            novo_pedido = Pedido(
                data_pedido=data_pedido,
                numero_mesa=numero_mesa,
                id_lanche=id_lanche,
                id_bebida=id_bebida,
                id_pessoa=id_pessoa,
                detalhamento=detalhamento,
                ajustes_receita=json.dumps(receita_final_str_keys),
                status=False,
                status_fechado=False
            )

            db_session.add(novo_pedido)
            db_session.flush()

            pedido_dict = novo_pedido.serialize()
            pedido_dict["ajustes_receita"] = {
                int(k): v for k, v in receita_final_str_keys.items()
            }
            pedido_dict["tipo_pedido"] = tipo_pedido

            pedidos_registrados.append(pedido_dict)

        db_session.commit()

        return jsonify({
            "success": f"{qtd_lanche} pedido(s) registrado(s) com sucesso ({tipo_pedido})",
            "pedidos": pedidos_registrados
        }), 201

    except Exception as e:
        db_session.rollback()
        print("ERRO cadastrar_pedido:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        db_session.close()



@app.route('/insumos', methods=['POST'])
# @jwt_required()
# @roles_required('admin')
def cadastrar_insumo():
    """
       API para cadastrar novos insumos utilizados nos lanches.

       # Endpoint:
       POST /insumos

       ## Corpo da Requisição (JSON)
       {
           "nome_insumo": "Tomate",
           "categoria_id": 1,
           "custo": 5.40
       }

       ## Resposta (JSON)
       {
           "success": "Insumo cadastrado com sucesso",
           "insumos": { ... }
       }
       """
    db_session = local_session()
    try:
        dados_insumo = request.get_json()

        campos_obrigatorios = ["nome_insumo", "categoria_id", "custo"]

        if not all(campo in dados_insumo for campo in campos_obrigatorios):
            return jsonify({"error": "Campo inexistente"}), 400

        if any(not dados_insumo[campo] for campo in campos_obrigatorios):
            return jsonify({"error": "Preencher todos os campos"}), 400

        else:
            form_novo_insumo = Insumo(
                nome_insumo=dados_insumo['nome_insumo'],
                categoria_id=dados_insumo['categoria_id'],
                custo=dados_insumo['custo'],
            )
            print(form_novo_insumo)
            form_novo_insumo.save(db_session)

            dicio = form_novo_insumo.serialize()
            resultado = {"success": "Insumo cadastrado com sucesso", "insumos": dicio}

            return jsonify(resultado), 201

    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route("/lanche_insumos", methods=["POST"])
# @jwt_required()
# @roles_required('admin')
def cadastrar_lanche_insumo():
    """
        API para vincular um insumo à receita de um lanche.

        # Endpoint:
        POST /lanche_insumos

        ## Corpo da Requisição (JSON)
        {
            "lanche_id": 1,
            "insumo_id": 3,
            "qtd_insumo": 100
        }

        ## Resposta (JSON)
        {
            "success": "Insumo adicionado à receita do lanche com sucesso",
            "lanche_insumo": { ... }
        }
        """
    dados = request.json
    # Verificar campos obrigatórios
    campos_obrigatorios = ["lanche_id", "insumo_id", "qtd_insumo"]
    if not all(campo in dados for campo in campos_obrigatorios):
        return jsonify({"error": "Campos obrigatórios não informados"}), 400

    if any(dados[campo] == "" for campo in campos_obrigatorios):
        return jsonify({"error": "Preencher todos os campos"}), 400

    lanche_id = dados["lanche_id"]
    insumo_id = dados["insumo_id"]
    qtd_insumo = dados["qtd_insumo"]

    # Verificar se o lanche existe
    # lanche = local_session.query(Lanche).filter_by(id_lanche=lanche_id).first()
    lanche = local_session.execute(select(Lanche).filter_by(id_lanche=lanche_id)).first()
    if not lanche:
        return jsonify({"error": "Lanche não encontrado"}), 404

    # Verificar se o insumo existe
    # insumo = local_session.query(Insumo).filter_by(id_insumo=insumo_id).first()
    insumo = local_session.execute(select(Insumo).filter_by(id_insumo=insumo_id)).first()
    if not insumo:
        return jsonify({"error": "Insumo não encontrado"}), 404

    # Verificar se esse insumo já está vinculado ao lanche
    # ja_existe = local_session.query(Lanche_insumo).filter_by(
    #     lanche_id=lanche_id, insumo_id=insumo_id
    # ).first()
    ja_existe = local_session.execute(select(Lanche_insumo).filter_by(lanche_id=lanche_id, insumo_id=insumo_id)).first()

    if ja_existe:
        return jsonify({"error": "Esse insumo já está vinculado a esse lanche"}), 409

    try:
        qtd = int(qtd_insumo)
        if qtd <= 0:
            return jsonify({"error": "Quantidade deve ser maior que zero"}), 400
    except ValueError:
        return jsonify({"error": "Quantidade deve ser numérica"}), 400

    # Criar o vínculo lanche-insumo
    novo_item_receita = Lanche_insumo(
        lanche_id=lanche_id,
        insumo_id=insumo_id,
        qtd_insumo=qtd
    )

    try:
        novo_item_receita.save(local_session)
        return jsonify({
            "success": "Insumo adicionado à receita do lanche com sucesso",
            "lanche_insumo": novo_item_receita.serialize()
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/vendas', methods=['POST'])
def cadastrar_venda():
    db_session = local_session()

    try:
        dados = request.get_json()

        if not dados:
            return jsonify({"error": "JSON inválido"}), 400

        campos = ["data_venda", "pessoa_id", "qtd_lanche", "detalhamento"]

        if not all(campo in dados for campo in campos):
            return jsonify({"error": "Campos obrigatórios não informados"}), 400

        # --- CAMPOS ---
        lanche_id = dados.get("lanche_id")
        pessoa_id = dados["pessoa_id"]
        bebida_id = dados.get("bebida_id")
        data_venda = dados["data_venda"]
        detalhamento = dados["detalhamento"]
        qtd_lanche = int(dados["qtd_lanche"])
        endereco = dados.get("endereco", "Presencial")
        forma_pagamento = dados.get("forma_pagamento", "Indefinido")

        # 🔥 Nunca deixar observacoes como None
        observacoes = dados.get("observacoes") or {"adicionar": [], "remover": []}

        valor_venda = float(dados.get("valor_venda", 0))

        # --- VALIDAR PESSOA ---
        pessoa = db_session.execute(
            select(Pessoa).filter_by(id_pessoa=pessoa_id)
        ).scalar_one_or_none()

        if not pessoa:
            return jsonify({"error": "Pessoa não encontrada"}), 404

        # Normalizar IDs
        lanche_id = lanche_id if lanche_id not in ("", None, "null") else None
        bebida_id = bebida_id if bebida_id not in ("", None, "null") else None

        receita_final_str_keys = {}

        # -------- PROCESSAMENTO DO LANCHE ----------
        if lanche_id:

            lanche = db_session.execute(
                select(Lanche).filter_by(id_lanche=lanche_id)
            ).scalar_one_or_none()

            if not lanche:
                return jsonify({"error": "Lanche não encontrado"}), 404

            # 🔥 CORREÇÃO AQUI (.scalars())
            receita = db_session.execute(
                select(Lanche_insumo).filter_by(lanche_id=lanche_id)
            ).scalars().all()

            receita_final = {
                item.insumo_id: item.qtd_insumo for item in receita
            }

            print("DEBUG observacoes recebidas:", observacoes)

            # REMOVER
            for rem in observacoes.get("remover", []):
                insumo_id = rem.get("insumo_id")
                qtd = rem.get("qtd", 0)

                if insumo_id is None:
                    continue

                insumo_id = int(insumo_id)

                if insumo_id in receita_final:
                    receita_final[insumo_id] = max(
                        0, receita_final[insumo_id] - qtd * 100
                    )

            # ADICIONAR
            for add in observacoes.get("adicionar", []):
                insumo_id = add.get("insumo_id")
                qtd = add.get("qtd", 0)

                if insumo_id is None:
                    continue

                insumo_id = int(insumo_id)

                receita_final[insumo_id] = receita_final.get(insumo_id, 0) + qtd * 100

            # 🔥 AGORA SIM preenche corretamente
            receita_final_str_keys = {
                str(k): v for k, v in receita_final.items()
            }

        # Nenhum item enviado
        if not lanche_id and not bebida_id:
            return jsonify(
                {"error": "É necessário informar pelo menos um lanche ou uma bebida"}
            ), 400

        # -------- SALVAR VENDA ----------
        nova_venda = Venda(
            data_venda=data_venda,
            lanche_id=lanche_id,
            pessoa_id=pessoa_id,
            bebida_id=bebida_id,
            valor_venda=valor_venda,
            detalhamento=detalhamento,
            status_venda=True,
            endereco=endereco,
            forma_pagamento=forma_pagamento,
            ajustes_receita=json.dumps(receita_final_str_keys)
        )

        nova_venda.save(db_session)

        venda_dict = nova_venda.serialize()
        venda_dict["ajustes_receita"] = {
            int(k): v for k, v in receita_final_str_keys.items()
        }

        return jsonify({
            "success": "Venda registrada com sucesso",
            "venda": venda_dict
        }), 201

    except Exception as e:
        db_session.rollback()
        print("ERRO cadastrar_venda:", str(e))
        return jsonify({"error": str(e)}), 500

    finally:
        db_session.close()



@app.route('/categorias', methods=['POST'])
# @jwt_required()
# @roles_required('admin')
def cadastrar_categoria():
    """
        API para cadastrar categorias de bebidas, lanches e insumos.

        # Endpoint:
        POST /categorias

        ## Corpo da Requisição (JSON)
        {
            "nome_categoria": "Refrigerantes"
        }

        ## Resposta (JSON)
        {
            "success": "Categoria cadastrada com sucesso",
            "categorias": { ... }
        }
        """
    db_session = local_session()
    try:
        dados_categoria = request.get_json()

        if not 'nome_categoria' in dados_categoria:
            return jsonify({
                "error": "Campo inexistente",
            })
        if dados_categoria['nome_categoria'] == "":
            return jsonify({
                "error": "Preencher todos os campos"
            })
        else:
            nome_categoria = dados_categoria['nome_categoria']
            form_nova_categoria = Categoria(
                nome_categoria=nome_categoria,
            )
            print(form_nova_categoria)
            form_nova_categoria.save(db_session)

            dicio = form_nova_categoria.serialize()
            resultado = {"success": "Categoria cadastrada com sucesso", "categorias": dicio}

            return jsonify(resultado), 201
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


# LISTAR (GET)

@app.route('/pedidos', methods=['GET'])
def pedidos():
    """
        GET /pedidos
        ---------------------------
        Retorna a lista de pedidos cadastrados.

         Exemplo de resposta:
        {
            "pedidos": [
                {
                    "id_pedido": 1,
                    "numero_da_mesa": 5,
                    "id_lanche": 2,
                    "id_bebida": 1,
                    "detalhamento": "Sem cebola",
                    "status": "em preparo"
                }
            ]
        }
        """
    db_session = local_session()
    try:
        sql_pedidos = select(Pedido).order_by(Pedido.id_pedido.desc())

        pedido_resultado = db_session.execute(sql_pedidos).scalars()
        pedidos = []
        for n in pedido_resultado:
            pedidos.append(n.serialize())
            print(pedidos[-1])
        return jsonify({
            "pedidos": pedidos
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/vendas/receitas', methods=['GET'])
# @jwt_required()
# @roles_required('cozinha', 'admin')
def listar_receitas_vendas():
    """
       GET /vendas/receitas
       ---------------------------------
       Retorna todas as vendas ativas com suas receitas completas,
       incluindo ajustes feitos na venda.

        Exemplo de resposta:
       {
           "vendas_receitas": [
               {
                   "venda_id": 10,
                   "lanche": "X-Burger",
                   "pessoa_id": 4,
                   "receita_completa": [
                       {"insumo_id": 1, "nome": "Pão", "quantidade": 1},
                       {"insumo_id": 2, "nome": "Carne", "quantidade": 1}
                   ]
               }
           ]
       }
       """
    db_session = local_session()
    try:
        # Pega apenas vendas ativas
        # vendas = db_session.query(Venda).filter_by(status_venda=True).all()
        vendas = db_session.execute(select(Venda).filter_by(status_venda=True)).all()
        vendas_receitas = []

        for venda in vendas:
            # lanche = db_session.query(Lanche).filter_by(id_lanche=venda.lanche_id).first()
            lanche = db_session.execute(select(Lanche).filter_by(id_lanche=venda.lanche_id)).first()
            if not lanche:
                continue

            # Receita base do lanche
            # receita_base = db_session.query(Lanche_insumo).filter_by(lanche_id=lanche.id_lanche).all()
            receita_base = db_session.execute(select(Lanche_insumo).filter_by(lanche_id=lanche.id_lanche)).all()
            receita_dict = {str(item.insumo_id): item.qtd_insumo for item in receita_base}

            # Aplicar ajustes da venda
            if hasattr(venda, "ajustes_receita") and venda.ajustes_receita:
                ajustes = json.loads(venda.ajustes_receita)
                for insumo_id, qtd in ajustes.items():
                    receita_dict[str(insumo_id)] = qtd  # sobrescreve ou adiciona

            # Transformar em lista de insumos com nome
            receita_completa = []
            for insumo_id, qtd in receita_dict.items():
                # insumo = db_session.query(Insumo).filter_by(id_insumo=int(insumo_id)).first()
                insumo = db_session.execute(select(Insumo).filter_by(id_insumo=int(insumo_id))).first()
                if insumo:
                    receita_completa.append({
                        "insumo_id": insumo.id_insumo,
                        "nome": insumo.nome_insumo,
                        "quantidade": qtd
                    })

            vendas_receitas.append({
                "venda_id": venda.id_venda,
                "lanche": lanche.nome_lanche,
                "pessoa_id": venda.pessoa_id,
                "receita_completa": receita_completa
            })

        return jsonify({"vendas_receitas": vendas_receitas}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db_session.close()


@app.route('/lanches', methods=['GET'])
# @jwt_required()
# @roles_required('cliente', 'garcom', 'cozinha', 'admin')
def listar_lanches():
    """
        GET /lanches
        ---------------------------
        Lista todos os lanches cadastrados.

         Exemplo de resposta:
        {
            "lanches": [
                {
                    "id_lanche": 1,
                    "nome_lanche": "X-Burger",
                    "descricao_lanche": "Pão, carne e queijo",
                    "valor_lanche": 25.90
                }
            ],
            "success": "Listado com sucesso"
        }
        """
    db_session = local_session()
    try:
        sql_lanche = select(Lanche)
        resultado_lanches = db_session.execute(sql_lanche).scalars()
        lanches = []

        for n in resultado_lanches:
            lanches.append(n.serialize())
            print(lanches[-1])
        return jsonify({
            "lanches": lanches,
            "success": "Listado com sucesso",
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/bebidas', methods=['GET'])
# @jwt_required()
# @roles_required('cliente', 'garcom', 'cozinha', 'admin')
def listar_bebidas():
    db_session = local_session()
    try:
        sql_bebidas = select(Bebida)
        resultado_bebidas = db_session.execute(sql_bebidas).scalars()
        bebidas = []

        for n in resultado_bebidas:
            bebidas.append(n.serialize())
            print(bebidas[-1])
        return jsonify({
            "bebidas": bebidas,
            "success": "Listado com sucesso",
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/insumos', methods=['GET'])
# @jwt_required()
# @roles_required('admin')
def listar_insumos():
    """
        GET /insumos
        ---------------------------
        Lista todos os insumos cadastrados.

         Exemplo de resposta:
        {
            "insumos": [
                {
                    "id_insumo": 3,
                    "nome_insumo": "Queijo",
                    "qtd_insumo": 20,
                    "validade": "2025-04-20",
                    "categoria_id": 1
                }
            ],
            "success": "Listado com sucesso"
        }
        """
    db_session = local_session()
    try:

        sql_insumos = select(Insumo)
        resultado_insumos = db_session.execute(sql_insumos).scalars()
        insumos = []
        for n in resultado_insumos:
            insumos.append(n.serialize())
            print(insumos[-1])
        return jsonify({
            "insumos": insumos,
            "success": "Listado com sucesso",
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/lanche_insumos', methods=['GET'])
# @jwt_required()
# @roles_required('admin')
def listar_lanche_insumos():
    """
       GET /lanche_insumos
       ---------------------------
       Lista a tabela que relaciona lanches e insumos.

       Exemplo de resposta:
       {
           "lanche_insumos": [
               {
                   "id": 1,
                   "lanche_id": 2,
                   "insumo_id": 3,
                   "qtd_insumo": 1
               }
           ],
           "success": "Listado com sucesso"
       }
       """
    db_session = local_session()
    try:

        sql_lanche_insumo = select(Lanche_insumo)
        resultado_lanche_insumos = db_session.execute(sql_lanche_insumo).scalars()
        lanche_insumos = []

        for n in resultado_lanche_insumos:
            lanche_insumos.append(n.serialize())
            print(lanche_insumos[-1])
        return jsonify({
            "lanche_insumos": lanche_insumos,
            "success": "Listado com sucesso",
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/lanche_receita/<int:lanche_id>', methods=['GET'])
# @jwt_required()
# @roles_required('cozinha', 'admin')
def listar_receita_lanche(lanche_id):
    """
       GET /lanche_receita/<lanche_id>
       ---------------------------------------------
       Retorna a receita base de um lanche específico.

        Parâmetro:
           lanche_id (int) — ID do lanche.

        Exemplo de resposta:
       {
           "lanche_id": 2,
           "nome_lanche": "X-Burger",
           "receita": [
               {"insumo_id": 1, "nome_insumo": "Pão", "quantidade_base": 1},
               {"insumo_id": 2, "nome_insumo": "Carne", "quantidade_base": 1}
           ]
       }
       """
    db_session = local_session()
    try:
        # Verifica se o lanche existe
        # lanche = db_session.query(Lanche).filter_by(id_lanche=lanche_id).first()
        lanche = db_session.scalars(select(Lanche).filter_by(id_lanche=lanche_id)).first()
        if not lanche:
            return jsonify({"error": "Lanche não encontrado"}), 404

        # Pega os insumos do lanche
        # lanche_insumos = db_session.query(Lanche_insumo).filter_by(lanche_id=lanche_id).all()
        lanche_insumos = db_session.scalars(
            select(Lanche_insumo).filter_by(lanche_id=lanche_id)
        ).all()
        if not lanche_insumos:
            return jsonify({"error": "Este lanche não possui insumos cadastrados"}), 400

        # Monta a receita
        receita = []
        for item in lanche_insumos:
            # insumo = db_session.query(Insumo).filter_by(id_insumo=item.insumo_id).first()
            insumo = db_session.scalars(
                select(Insumo).filter_by(id_insumo=item.insumo_id)
            ).first()
            if insumo:
                receita.append({
                    "insumo_id": insumo.id_insumo,
                    "nome_insumo": insumo.nome_insumo,
                    "quantidade_base": item.qtd_insumo
                })

        return jsonify({
            "lanche_id": lanche.id_lanche,
            "nome_lanche": lanche.nome_lanche,
            "receita": receita
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db_session.close()


@app.route('/categorias', methods=['GET'])
# @jwt_required()
# @roles_required('admin')
def listar_categorias():
    """
       GET /categorias
       ---------------------------
       Lista todas as categorias de insumos.

        Exemplo de resposta:
       {
           "categorias": [
               {
                   "id_categoria": 1,
                   "nome_categoria": "Carnes"
               }
           ],
           "success": "Listado com sucesso"
       }
       """
    db_session = local_session()
    try:
        sql_categorias = select(Categoria)
        resultado_categorias = db_session.execute(sql_categorias).scalars()
        categorias = []
        for n in resultado_categorias:
            categorias.append(n.serialize())
            print(categorias[-1])
        return jsonify({
            "categorias": categorias,
            "success": "Listado com sucesso",
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/entradas', methods=['GET'])
# @jwt_required()
# @roles_required('admin')
def listar_entradas():
    """
    GET /entradas
    ---------------------------
    Lista todas as entradas de estoque registradas.

     Exemplo de resposta:
    {
        "entradas": [
            {
                "id_entrada": 5,
                "qtd_entrada": 10,
                "data_entrada": "2025-03-10",
                "valor_entrada": 150,
                "insumo_id": 2
            }
        ],
        "success": "Listado com sucesso"
    }
    """
    db_session = local_session()
    try:
        sql_entradas = select(Entrada)
        resultado_entradas = db_session.execute(sql_entradas).scalars()
        entradas = []
        for n in resultado_entradas:
            entradas.append(n.serialize())
            print(entradas[-1])
        return jsonify({
            "entradas": entradas,
            "success": "Listado com sucesso",
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/vendas_id/<id_mesa>', methods=['GET'])
# @jwt_required()
# @roles_required('admin')
def listar_vendas_id(id_mesa):
    """
      GET /vendas_id/<id_mesa>
      -----------------------------------
      Retorna a venda vinculada a uma mesa específica.

       Parâmetro:
          id_mesa (int)

       Exemplo de resposta:
      {
          "sucesso": "venda encontrada com sucesso",
          "id_venda": 12,
          "data_venda": "2025-03-10",
          "valor_venda": 39.90,
          "status_venda": true,
          "mesa": 5,
          "lanche_id": 1,
          "pessoa_id": 3
      }
      """
    db_session = local_session()
    try:
        sql_vendas = db_session.execute(select(Venda).where(mesa=id_mesa)).scalar()
        if not sql_vendas:
            return jsonify({'error': 'venda não encontrada'})
        return jsonify({"sucesso": "venda encontrada com sucesso",
                        "id_venda": sql_vendas.id_venda,
                        "data_venda": sql_vendas.data_venda,
                        "valor_venda": sql_vendas.valor_venda,
                        "status_venda": sql_vendas.status_venda,
                        "mesa": sql_vendas.mesa,
                        "lanche_id": sql_vendas.lanche_id,
                        "pessoa_id": sql_vendas.pessoa_id})

    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/vendas', methods=['GET'])
# @jwt_required()
# @roles_required('admin')
def listar_vendas():
    """
     GET /vendas
     ---------------------------
     Lista todas as vendas cadastradas.

      Exemplo de resposta:
     {
         "vendas": [
             {
                 "id_venda": 12,
                 "mesa": 5,
                 "valor_venda": 39.90,
                 "status_venda": true
             }
         ]
     }
     """
    db_session = local_session()
    try:
        sql_vendas = select(Venda).order_by(Venda.id_venda.desc())

        venda_resultado = db_session.execute(sql_vendas).scalars()
        vendas = []
        for n in venda_resultado:
            vendas.append(n.serialize())
            print(vendas[-1])
        return jsonify({
            "vendas": vendas
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/pessoas', methods=['GET'])
# @jwt_required()
# @roles_required('admin')
def listar_pessoas():
    """
       GET /pessoas
       ---------------------------
       Lista todas as pessoas cadastradas no sistema.

       Exemplo de resposta:
       {
           "pessoas": [
               {
                   "id_pessoa": 1,
                   "nome_pessoa": "João Silva",
                   "email": "joao@gmail.com",
                   "papel": "garcom"
               }
           ],
           "success": "Listado com sucesso"
       }
       """
    db_session = local_session()
    try:
        sql_pessoa = select(Pessoa)
        resultado_pessoas = db_session.execute(sql_pessoa).scalars()
        pessoas = []
        for n in resultado_pessoas:
            pessoas.append(n.serialize())
            print(pessoas[-1])

        return jsonify({
            "pessoas": pessoas,
            "success": "Listado com sucesso"
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/id_pessoa/<id_pessoa>', methods=['GET'])
# @jwt_required()
# @roles_required('admin')
def listar_pessoa_by_id(id_pessoa):
    """
        GET /pessoas/pessoa<id_pessoa>
        -----------------------------------
        Retorna uma pessoa específica pelo ID.

        🔹 Exemplo de resposta:
        {
            "pessoa": {
                "id_pessoa": 3,
                "nome_pessoa": "Maria",
                "email": "maria@gmail.com"
            },
            "success": "Listado com sucesso"
        }
        """
    db_session = local_session()
    try:
        sql_pessoa = select(Pessoa).filter_by(id_pessoa=Pessoa.id_pessoa)
        resultado_pessoa = db_session.execute(sql_pessoa).scalar()
        # pessoas = []
        # for n in resultado_pessoa:
        #     pessoas.append(n.serialize())
        #     print(pessoas[-1])

        return jsonify({
            "pessoa": resultado_pessoa.serialize(),
            "success": "Listado com sucesso"
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/get_insumo_id/<id_insumo>', methods=['GET'])
def get_insumo_id(id_insumo):
    db_session = local_session()
    try:
        insumo = db_session.execute(
            select(Insumo).filter_by(id_insumo=int(id_insumo))
        ).scalar_one_or_none()

        if not insumo:
            return jsonify({
                "error": "Insumo não encontrado"
            }), 404

        return jsonify({
            "success": "Insumo encontrado com sucesso",
            "id_insumo": insumo.id_insumo,
            "nome_insumo": insumo.nome_insumo,
            "qtd_insumo": insumo.qtd_insumo,
            "custo": insumo.custo,
            "categoria_id": insumo.categoria_id,
        })

    except ValueError:
        return jsonify({
            "error": "ID do insumo deve ser numérico"
        }), 400

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

    finally:
        db_session.close()


@app.route('/categorias/categoria<id_categoria>', methods=['GET'])
# @jwt_required()
# @roles_required('admin')
def listar_cateogira_by_id(id_categoria):
    """
       GET /categorias/categoria<id_categoria>
       ------------------------------------------------
       Retorna uma categoria específica.

        Exemplo de resposta:
       {
           "categoria": {
               "id_categoria": 1,
               "nome_categoria": "Verduras"
           },
           "success": "Listado com sucesso"
       }
       """
    db_session = local_session()
    try:
        sql_categoria = select(Categoria).filter_by(id_categoria=Categoria.id_categoria)
        resultado = db_session.execute(sql_categoria).scalar()
        # pessoas = []
        # for n in resultado_pessoas:
        #     pessoas.append(n.serialize())
        #     print(pessoas[-1])

        return jsonify({
            "categoria": resultado.serialize(),
            "success": "Listado com sucesso"
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


# EDITAR (PUT)
@app.route('/pedidos/mesa', methods=['PUT'])
def editar_pedidos_numero_mesa():  # Função para fechar a conta
    """
       PUT /pedidos/mesa
       ----------------------------------------------------
       Retorna todos os pedidos associados a uma mesa específica.

        Corpo da requisição (JSON):
       {
           "numero_mesa": 7
       }

        O que faz:
           - Recebe o número da mesa.
           - Busca no banco todos os pedidos daquela mesa.
           - Serializa e retorna os pedidos encontrados.

        Exemplo de resposta:
       {
           "pedidos": [
               {
                   "id_pedido": 3,
                   "numero_mesa": 7,
                   "lanche_id": 2,
                   "status": true
               }
           ]
       }
       """
    try:
        db_session = local_session()
        dados = request.get_json()
        pedidos_ = db_session.execute(
            select(Pedido).filter_by(numero_mesa=int(dados['numero_mesa']))).scalars()
        resultado = []
        for p in pedidos_:
            resultado.append(p.serialize())
            itens_total = []
        for pedidos_ in resultado:
            return jsonify({"pedidos": resultado})
    except Exception as e:
        return jsonify({'error': f'{e}'})


@app.route('/pedidos/<id_pedido>', methods=['PUT'])
def editar_pedido_status(id_pedido):  # editar pedido status
    """
       PUT /pedidos/<id_pedido>
       ----------------------------------------------------
       Registra a venda de um pedido, ajusta estoque e gera movimentos
       de venda relacionados ao pedido.

        Parâmetro:
           id_pedido (int)

        Corpo esperado:
       {
           "data_venda": "2025-01-25 12:30:00",
           "lanche_id": 3,
           "pessoa_id": 5,
           "qtd_lanche": 2,
           "detalhamento": "Pedido mesa 7",
           "endereco": "Retirada no balcão",
           "forma_pagamento": "Crédito",
           "observacoes": {
               "adicionar": [{"insumo_id": 1, "qtd": 1}],
               "remover": [{"insumo_id": 2, "qtd": 1}]
           }
       }

        O que faz:
           - Valida campos necessários.
           - Verifica lanche e pessoa.
           - Carrega receita base do lanche.
           - Ajusta insumos conforme observações.
           - Verifica estoque.
           - Dá baixa no estoque.
           - Cria registros de venda.
           - Retorna as vendas geradas.

        Exemplo de resposta:
       {
           "success": "2 vendas registradas com sucesso",
           "vendas": [
               {
                   "id_venda": 20,
                   "valor_venda": 18.50,
                   "ajustes_receita": { "1": 200, "3": 100 }
               }
           ]
       }
       """
    db_session = local_session()
    try:
        dados = request.get_json()
        campos = ["data_venda", "lanche_id", "pessoa_id", "qtd_lanche", "detalhamento"]

        if not all(campo in dados for campo in campos):
            return jsonify({"error": "Campos obrigatórios não informados"}), 400

        lanche_id = dados["lanche_id"]
        pessoa_id = dados["pessoa_id"]
        data_venda = dados["data_venda"]
        detalhamento = dados["detalhamento"]
        qtd_lanche = int(dados["qtd_lanche"])
        endereco = dados['endereco']
        forma_pagamento = dados['forma_pagamento']

        observacoes = dados.get("observacoes", {"adicionar": [], "remover": []})
        lanche = db_session.execute(select(Lanche).filter_by(id_lanche=lanche_id)).first()
        # lanche = db_session.query(Lanche).filter_by(id_lanche=lanche_id).first()
        pessoa = db_session.execute(select(Pessoa).filter_by(id_pessoa=pessoa_id)).first()
        # pessoa = db_session.query(Pessoa).filter_by(id_pessoa=pessoa_id).first()

        if not lanche:
            return jsonify({"error": "Lanche não encontrado"}), 404
        if not pessoa:
            return jsonify({"error": "Pessoa não encontrada"}), 404

        # Receita base do lanche
        receita = db_session.execute(select(Lanche_insumo).filter_by(lanche_id=lanche_id)).all()
        # receita = db_session.query(Lanche_insumo).filter_by(lanche_id=lanche_id).all()
        if not receita:
            return jsonify({"error": "Esse lanche não tem receita cadastrada"}), 400

        # Montar receita ajustada
        receita_final = {item.insumo_id: item.qtd_insumo for item in receita}

        # Remover insumos
        for rem in observacoes.get("remover", []):
            if rem["insumo_id"] in receita_final:
                receita_final[rem["insumo_id"]] = max(
                    0, receita_final[rem["insumo_id"]] - rem["qtd"] * 100
                )

        # Adicionar insumos extras
        for add in observacoes.get("adicionar", []):
            receita_final[add["insumo_id"]] = receita_final.get(add["insumo_id"], 0) + add["qtd"] * 100

        # Verificar estoque
        for insumo_id, qtd in receita_final.items():
            insumo = db_session.execute(select(Insumo).filter_by(id_insumo=insumo_id)).first()
            # insumo = db_session.query(Insumo).filter_by(id_insumo=insumo_id).first()
            if not insumo:
                return jsonify({"error": f"Insumo ID {insumo_id} não encontrado"}), 404
            if insumo.qtd_insumo < qtd * qtd_lanche:
                return jsonify({"error": f"Estoque insuficiente para: {insumo.nome_insumo}"}), 400

        # Dar baixa nos insumos
        for insumo_id, qtd in receita_final.items():
            insumo = db_session.execute(select(Insumo).filter_by(id_insumo=insumo_id)).first()
            # insumo = db_session.query(Insumo).filter_by(id_insumo=insumo_id).first()
            insumo.qtd_insumo -= qtd * qtd_lanche
            db_session.add(insumo)

        # Converter chaves para string antes de salvar
        receita_final_str_keys = {str(k): v for k, v in receita_final.items()}

        # Registrar vendas
        vendas_registradas = []
        for _ in range(qtd_lanche):
            nova_venda = Venda(
                data_venda=data_venda,
                lanche_id=lanche_id,
                pessoa_id=pessoa_id,
                valor_venda=lanche.valor_lanche,
                detalhamento=detalhamento,
                status_venda=True,
                endereco=endereco,
                forma_pagamento=forma_pagamento,
                ajustes_receita=json.dumps(receita_final_str_keys)
            )
            nova_venda.save(db_session)
            venda_dict = nova_venda.serialize()
            # converter de volta para int no retorno
            venda_dict["ajustes_receita"] = {int(k): v for k, v in receita_final_str_keys.items()}
            vendas_registradas.append(venda_dict)

        return jsonify({
            "success": f"{qtd_lanche} vendas registradas com sucesso",
            "vendas": vendas_registradas
        }), 201

    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db_session.close()


@app.route('/lanches/<id_lanche>', methods=['PUT'])
# @jwt_required()
def editar_lanche(id_lanche):
    """
       PUT /lanches/<id_lanche>
       ----------------------------------------------------
       Edita as informações de um lanche existente.

        Parâmetro:
           id_lanche (int)

        Corpo esperado:
       {
           "nome_lanche": "X-Burguer",
           "descricao_lanche": "Pão, carne e queijo",
           "valor_lanche": 15.90
       }

        O que faz:
           - Verifica se o lanche existe.
           - Valida campos obrigatórios.
           - Atualiza nome, descrição e valor.
           - Salva e retorna o lanche atualizado.

        Exemplo de resposta:
       {
           "success": "lanche editado com sucesso",
           "lanches": { ...dados... }
       }
       """
    db_session = local_session()
    try:
        dados_editar_lanche = request.get_json()

        lanche_resultado = db_session.execute(select(Lanche).filter_by(id_lanche=int(id_lanche))).scalar()
        print(lanche_resultado)

        if not lanche_resultado:
            return jsonify({"error": "Lanche não encontrado"}), 400

        campos_obrigatorios = ["nome_lanche", "descricao_lanche", "valor_lanche"]

        if not all(campo in dados_editar_lanche for campo in campos_obrigatorios):
            return jsonify({"error": "Campo inexistente"}), 400

        if any(not dados_editar_lanche[campo] for campo in campos_obrigatorios):
            return jsonify({"error": "Preencher todos os campos"}), 400

        else:
            lanche_resultado.nome_lanche = dados_editar_lanche['nome_lanche']
            lanche_resultado.valor_lanche = dados_editar_lanche['valor_lanche']
            lanche_resultado.descricao_lanche = dados_editar_lanche['descricao_lanche']

            lanche_resultado.save(db_session)
            dicio = lanche_resultado.serialize()
            resultado = {"success": "lanche editado com sucesso", "lanches": dicio}

            return jsonify(resultado), 201

    except ValueError:
        return jsonify({
            "error": "Valor inserido inválido"
        }), 400

    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/insumos/<id_insumo>', methods=['PUT'])  #
# @jwt_required()
def editar_insumo(id_insumo):
    """
        PUT /insumos/<id_insumo>
        ----------------------------------------------------
        Edita informações de um insumo.

         Parâmetro:
            id_insumo (int)

         Corpo esperado:
        {
            "nome_insumo": "Tomate",
            "categoria_id": 1
        }

         O que faz:
            - Verifica se o insumo existe.
            - Confere campos obrigatórios.
            - Atualiza nome e categoria.
            - Retorna insumo atualizado.

         Exemplo de resposta:
        {
            "success": "insumo editado com sucesso",
            "insumos": { ... }
        }
        """
    db_session = local_session()
    try:
        dados_editar_insumo = request.get_json()

        insumo_resultado = db_session.execute(select(Insumo).filter_by(id_insumo=int(id_insumo))).scalar()
        print(insumo_resultado)

        if not insumo_resultado:
            return jsonify({"error": "Insumo não encontrado"}), 400

        campos_obrigatorios = ["nome_insumo", "categoria_id"]

        if not all(campo in dados_editar_insumo for campo in campos_obrigatorios):
            return jsonify({"error": "Campo inexistente"}), 400

        if any(not dados_editar_insumo[campo] for campo in campos_obrigatorios):
            return jsonify({"error": "Preencher todos os campos"}), 400

        else:
            insumo_resultado.nome_insumo = dados_editar_insumo['nome_insumo']
            insumo_resultado.categoria_id = dados_editar_insumo['categoria_id']

            insumo_resultado.save(db_session)
            dicio = insumo_resultado.serialize()
            resultado = {"success": "insumo editado com sucesso", "insumos": dicio}

            return jsonify(resultado), 201

    except ValueError:
        return jsonify({
            "error": "Valor inserido inválido"
        }), 400

    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/categorias/<id_categoria>', methods=['PUT'])  #
# @jwt_required()
def editar_categoria(id_categoria):
    """
        PUT /categorias/<id_categoria>
        ----------------------------------------------------
        Edita o nome de uma categoria.

         Parâmetro:
            id_categoria (int)

         Corpo esperado:
        {
            "nome_categoria": "Bebidas"
        }

         O que faz:
            - Valida se a categoria existe.
            - Confere campo obrigatório.
            - Atualiza nome.
            - Retorna categoria atualizada.

         Exemplo de resposta:
        {
            "success": "categoria editada com sucesso",
            "categorias": { ... }
        }
        """
    db_session = local_session()
    try:
        dados_editar_categoria = request.get_json()

        categoria_resultado = db_session.execute(select(Categoria).filter_by(id_categoria=int(id_categoria))).scalar()
        print(categoria_resultado)

        if not categoria_resultado:
            return jsonify({
                "error": "Categoria não encontrada"
            })

        if not 'nome_categoria' in dados_editar_categoria:
            return jsonify({
                "error": "Campo inexistente"
            }), 400

        if dados_editar_categoria['nome_categoria'] == "":
            return jsonify({
                "error": "Preencher todos os campos"
            }), 400

        else:
            categoria_resultado.nome_categoria = dados_editar_categoria['nome_categoria']

            categoria_resultado.save(db_session)

            dicio = categoria_resultado.serialize()
            resultado = {"success": "categoria editado com sucesso", "categorias": dicio}

            return jsonify(resultado), 200

    except ValueError:
        return jsonify({
            "error": "Valor inserido inválido"
        }), 400

    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/pessoas/<id_pessoa>', methods=['PUT'])  #
# @jwt_required()
def editar_pessoa(id_pessoa):
    """
       PUT /pessoas/<id_pessoa>
       ----------------------------------------------------
       Edita os dados completos de uma pessoa.

        Parâmetro:
           id_pessoa (int)

        Corpo esperado:
       {
           "nome_pessoa": "João",
           "cpf": "12345678900",
           "salario": 2200,
           "papel": "garcom",
           "senha_hash": "HASH...",
           "email": "teste@gmail.com",
           "status_pessoa": "Ativo"
       }

        O que faz:
           - Valida existência da pessoa.
           - Confere todos os campos obrigatórios.
           - Atualiza dados cadastrados.
           - Retorna dados atualizados.

        Exemplo:
       {
           "success": "Pessoa editada com sucesso",
           "pessoas": { ... }
       }
       """
    db_session = local_session()
    try:
        dados_editar_pessoa = request.get_json()

        pessoa_resultado = db_session.execute(select(Pessoa).filter_by(id_pessoa=int(id_pessoa))).scalar()
        print(pessoa_resultado)

        if not pessoa_resultado:
            return jsonify({"error": "Pessoa não encontrada"}), 400

        # campos_obrigatorios = ["nome_pessoa", "cpf", "salario", "papel", "senha_hash", "email"]

        # if not all(campo in dados_editar_pessoa for campo in campos_obrigatorios):
        #     return jsonify({"error": "Campo inexistente"}), 400

        # if any(not dados_editar_pessoa[campo] for campo in campos_obrigatorios):
        #     return jsonify({"error": "Preencher todos os campos"}), 400

        else:
            pessoa_resultado.nome_pessoa = dados_editar_pessoa['nome_pessoa']
            pessoa_resultado.cpf = dados_editar_pessoa['cpf']
            pessoa_resultado.salario = dados_editar_pessoa['salario']
            pessoa_resultado.papel = dados_editar_pessoa['papel']
            # pessoa_resultado.senha_hash = dados_editar_pessoa['senha_hash']
            pessoa_resultado.email = dados_editar_pessoa['email']
            pessoa_resultado.status_pessoa = dados_editar_pessoa['status_pessoa']
            pessoa_resultado.save(db_session)

            dicio = pessoa_resultado.serialize()
            resultado = {"success": "Pessoa editada com sucesso", "pessoas": dicio}

            return jsonify(resultado), 200

    except ValueError:
        return jsonify({
            "error": "Valor inserido inválido"
        })

    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route("/lanche_insumo", methods=["DELETE"])
# @jwt_required()
def deletar_lanche_insumo():
    """
        DELETE /lanche_insumo
        ----------------------------------------------------
        Remove o vínculo entre um lanche e um insumo.

         Corpo da requisição:
        {
            "lanche_id": 3,
            "insumo_id": 8
        }

         O que faz:
            - Verifica se o vínculo existe.
            - Caso exista, remove.
            - Retorna confirmação.

         Exemplo de resposta:
        {
            "success": "Relacionamento removido com sucesso"
        }
        """
    dados = request.json

    # Verificação dos campos obrigatórios
    if not dados or "lanche_id" not in dados or "insumo_id" not in dados:
        return jsonify({"error": "Informe 'lanche_id' e 'insumo_id' no corpo da requisição"}), 400

    lanche_id = dados["lanche_id"]
    insumo_id = dados["insumo_id"]

    # Verificar se o vínculo existe
    # relacionamento = local_session.query(Lanche_insumo).filter_by(
    #     lanche_id=lanche_id, insumo_id=insumo_id
    # ).first()
    relacionamento = local_session.execute(
        select(Lanche_insumo).filter_by(lanche_id=lanche_id, insumo_id=insumo_id)).first()

    if not relacionamento:
        return jsonify({"error": "Esse insumo não está vinculado a esse lanche"}), 404

    try:
        relacionamento.delete(local_session)
        return jsonify({"success": "Relacionamento removido com sucesso"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/deletar_categoria/<id_categoria>", methods=["DELETE"])
def deletar_categoria(id_categoria):
    db_session = local_session()

    try:
        categoria_del = db_session.execute(select(Categoria).filter_by(id_categoria=int(id_categoria))).scalar()

        if not categoria_del:
            return jsonify({
                "error": 'Categoria não encontrada'
            })

        categoria_del.delete(db_session)
        return jsonify({
            "success": "Categoria deletada com sucesso"
        })

    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


# grafco de vendas
@app.route('/dados_grafico')
def dados_grafico():
    """
       GET /dados_grafico
       ----------------------------------------------------
       Retorna dados agregados de vendas por mês
       para exibição em gráficos de faturamento simples.

        O que faz:
           - Agrupa vendas por ano/mês.
           - Soma valor total de vendas.
           - Retorna labels e valores prontos para gráfico.

        Exemplo de resposta:
       {
           "labels": ["11/2025", "12/2025"],
           "values": [1200.50, 845.30]
       }
       """
    session = local_session()

    vendas = session.query(Venda).all()

    agrupado = {}

    for v in vendas:
        data = v.data_venda

        # Se veio como string, converter
        if isinstance(data, str):
            data = datetime.strptime(data, "%Y-%m-%d %H:%M:%S")

        ano = data.year
        mes = data.month
        chave = (ano, mes)

        if chave not in agrupado:
            agrupado[chave] = 0

        agrupado[chave] += v.valor_venda

    agrupado_ordenado = dict(sorted(agrupado.items()))

    labels = [f"{mes:02d}/{ano}" for (ano, mes) in agrupado_ordenado.keys()]
    valores = list(agrupado_ordenado.values())

    return jsonify({"labels": labels, "values": valores})


# -----------
# grafico de faturamento
# CORRETO
@app.route("/faturamento_mensal", methods=["GET"])
def faturamento_mensal():
    """
       GET /faturamento_mensal
       ----------------------------------------------------
       Retorna o faturamento mensal agregado (soma das vendas).

        O que faz:
           - Agrupa as vendas por mês.
           - Soma valores do mês.
           - Retorna lista com mês e valor.

        Exemplo de resposta:
       [
           {"mes": "2025-10", "faturamento": 1540.00},
           {"mes": "2025-11", "faturamento": 1870.90}
       ]
       """
    # vendas = local_session.query(Venda).all()
    db_session = local_session()
    # vendas = db_session.execute(select(Venda)).all()
    vendas = db_session.query(Venda).all()

    faturamento = defaultdict(float)

    for venda in vendas:
        try:
            # Converte string para datetime com hora
            data = datetime.strptime(venda.data_venda, "%Y-%m-%d %H:%M:%S")

            # Agrupa por ano-mês (ex: "2025-11")
            chave_mes = data.strftime("%Y-%m")

            faturamento[chave_mes] += venda.valor_venda

        except Exception as e:
            print("Erro:", venda.data_venda, e)

    resposta = [
        {"mes": mes, "faturamento": round(valor, 2)}
        for mes, valor in sorted(faturamento.items())
    ]
    return jsonify(resposta)


#
# @app.route('/vendas_valor_por_funcionario', methods=['GET'])
# def vendas_valor_por_funcionario():
#     """
#     GET /vendas_valor_por_funcionario
#     ----------------------------------------------------
#     Retorna, por funcionário, a quantidade de vendas e o
#     total vendido *no dia*.
#
#      Query Params:
#         ?date=YYYY-MM-DD      (default = hoje)
#         ?role=garcom
#         ?include_delivery=true/false
#         ?include_zeros=true/false
#
#      O que faz:
#         - Filtra vendas do dia.
#         - Opcionalmente filtra por papel.
#         - Agrupa por funcionário.
#         - Pode incluir funcionários com zero vendas.
#
#      Exemplo:
#     {
#         "labels": ["João", "Marcos"],
#         "counts": [3, 1],
#         "totals": [85.50, 22.00]
#     }
#     """
#     date_str = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')
#     role = request.args.get('role')                     # ex: "garcom"
#     include_delivery = request.args.get('include_delivery', 'false').lower() == 'true'
#     include_zeros = request.args.get('include_zeros', 'false').lower() == 'true'
#
#     db = local_session()
#     try:
#         # Base: vendas do dia (pega somente a parte YYYY-MM-
#         stmt = (
#             select(
#                 Venda.pessoa_id.label('pessoa_id'),
#                 func.count(Venda.id_venda).label('qtd'),
#                 func.coalesce(func.sum(Venda.valor_venda), 0).label('total')
#             )
#             .filter_by(func.substr(Venda.data_venda, 1, 10) == date_str)
#         )
#         # qry = db.query(
#         #     Venda.pessoa_id.label('pessoa_id'),
#         #     func.count(Venda.id_venda).label('qtd'),
#         #     func.coalesce(func.sum(Venda.valor_venda), 0).label('total')
#         # ).filter(func.substr(Venda.data_venda, 1, 10) == date_str)
#
#         # Se for para excluir deliveries e SE existir relacionamento via Pedido, usamos numero_mesa==0
#         # Tentativa segura: checar se as colunas existem e o modelo Pedido está presente
#         use_pedido_flag = False
#         try:
#             # checa se Venda tem coluna pedido_id e existe o modelo Pedido com numero_mesa
#             if 'pedido_id' in Venda.__table__.columns and 'numero_mesa' in Pedido.__table__.columns:
#                 use_pedido_flag = True
#         except Exception:
#             use_pedido_flag = False
#
#         if not include_delivery:
#             if use_pedido_flag:
#                 # join com Pedido e excluir where Pedido.numero_mesa == 0
#                 qry = qry.join(Pedido, Pedido.id_pedido == Venda.pedido_id).filter(Pedido.numero_mesa != 0)
#             else:
#                 # fallback: excluir quando endereco indica delivery ou endereco == '0' ou vazio
#                 qry = qry.filter(
#                     and_(
#                         not_(Venda.endereco.ilike('%delivery%')),
#                         not_(Venda.endereco.ilike('%entrega%')),
#                         Venda.endereco != '0',
#                         Venda.endereco != ''
#                     )
#                 )
#
#         # se pediu filtrar por papel, junta com Pessoa e filtra
#         if role:
#             qry = qry.join(Pessoa, Pessoa.id_pessoa == Venda.pessoa_id).filter(func.lower(Pessoa.papel) == role.lower())
#
#         rows = qry.group_by(Venda.pessoa_id).order_by(func.sum(Venda.valor_venda).desc()).all()
#
#         labels = []
#         counts = []
#         totals = []
#         ids_present = set()
#
#         for pessoa_id, qtd, total in rows:
#             pessoa = db.execute(select(Pessoa).filter_by(id_pessoa=pessoa_id)).first()
#             # pessoa = db.query(Pessoa).filter_by(id_pessoa=pessoa_id).first()
#             nome = pessoa.nome_pessoa if pessoa else f"ID {pessoa_id}"
#             labels.append(nome)
#             counts.append(int(qtd))
#             totals.append(float(total or 0))
#             ids_present.add(pessoa_id)
#
#         # incluir zeros: buscar todos os funcionários com o papel (ou todos se role None)
#         if include_zeros:
#             pquery = db.execute(select(Pessoa))
#             # pquery = db.query(Pessoa)
#             if role:
#                 pquery = pquery.filter(func.lower(Pessoa.papel) == role.lower())
#             pessoas = pquery.all()
#             for p in pessoas:
#                 if p.id_pessoa not in ids_present:
#                     labels.append(p.nome_pessoa)
#                     counts.append(0)
#                     totals.append(0.0)
#
#         return jsonify({
#             "date": date_str,
#             "role": role,
#             "include_delivery": include_delivery,
#             "labels": labels,
#             "counts": counts,
#             "totals": totals
#         })
#     finally:
#         db.close()

@app.route('/vendas_valor_por_funcionario_mes', methods=['GET'])
def vendas_valor_por_funcionario_mes():
    """
    GET /vendas_valor_por_funcionario_mes
    ----------------------------------------------------
    Retorna vendas agregadas por funcionário *no mês*.

     Query Params:
        ?month=YYYY-MM        (default = mês atual)
        ?role=garcom
        ?include_delivery=true/false
        ?include_zeros=true/false

     O que faz:
        - Filtra vendas do mês.
        - Agrupa por funcionário.
        - Retorna quantidade e valor total vendido.

     Exemplo:
    {
        "labels": ["João", "Marcos"],
        "counts": [15, 8],
        "totals": [420.00, 235.50]
    }
    """
    month_str = request.args.get('month') or datetime.now().strftime('%Y-%m')
    role = request.args.get('role')
    include_delivery = request.args.get('include_delivery', 'false').lower() == 'true'
    include_zeros = request.args.get('include_zeros', 'false').lower() == 'true'

    db = local_session()
    try:
        # Vendas do mês -- substr pega só o YYYY-MM
        qry = db.query(
            Venda.pessoa_id.label('pessoa_id'),
            func.count(Venda.id_venda).label('qtd'),
            func.coalesce(func.sum(Venda.valor_venda), 0).label('total')
        ).filter(func.substr(Venda.data_venda, 1, 7) == month_str)

        # Detectar se pode usar Pedido.numero_mesa == 0
        use_pedido_flag = False
        try:
            if 'pedido_id' in Venda.__table__.columns and 'numero_mesa' in Pedido.__table__.columns:
                use_pedido_flag = True
        except:
            use_pedido_flag = False

        # excluir delivery
        if not include_delivery:
            if use_pedido_flag:
                qry = qry.join(Pedido, Pedido.id_pedido == Venda.pedido_id).filter(Pedido.numero_mesa != 0)
            else:
                qry = qry.filter(
                    and_(
                        not_(Venda.endereco.ilike('%delivery%')),
                        not_(Venda.endereco.ilike('%entrega%')),
                        Venda.endereco != '0',
                        Venda.endereco != ''
                    )
                )

        # filtrar por papel
        if role:
            qry = qry.join(Pessoa, Pessoa.id_pessoa == Venda.pessoa_id) \
                .filter(func.lower(Pessoa.papel) == role.lower())

        # resultado agrupado
        rows = qry.group_by(Venda.pessoa_id) \
            .order_by(func.sum(Venda.valor_venda).desc()) \
            .all()

        labels = []
        counts = []
        totals = []
        ids_present = set()

        for pid, qtd, total in rows:
            pessoa = db.query(Pessoa).filter_by(id_pessoa=pid).first()
            nome = pessoa.nome_pessoa if pessoa else f"ID {pid}"
            labels.append(nome)
            counts.append(int(qtd))
            totals.append(float(total or 0))
            ids_present.add(pid)

        # incluir funcionários com 0 vendas
        if include_zeros:
            q = db.query(Pessoa)
            if role:
                q = q.filter(func.lower(Pessoa.papel) == role.lower())
            pessoas = q.all()

            for p in pessoas:
                if p.id_pessoa not in ids_present:
                    labels.append(p.nome_pessoa)
                    counts.append(0)
                    totals.append(0.0)

        return jsonify({
            "month": month_str,
            "role": role,
            "include_delivery": include_delivery,
            "labels": labels,
            "counts": counts,
            "totals": totals
        })

    finally:
        db.close()


@app.route('/vendas_hoje_por_funcionario', methods=['GET'])
def vendas_hoje_por_funcionario():
    print("aaaaaaaaaaaaaaaa")

    hoje = datetime.now().strftime('%Y-%m-%d')
    role = request.args.get('role')

    db = local_session()

    try:
        qry = db.query(
            Venda.pessoa_id.label('pessoa_id'),
            Pessoa.nome_pessoa.label('nome'),
            func.count(Venda.id_venda).label('qtd'),
            func.coalesce(func.sum(Venda.valor_venda), 0).label('total')
        ).join(Pessoa, Pessoa.id_pessoa == Venda.pessoa_id) \
         .filter(Venda.data_venda.like(f"{hoje}%"))  # 🔥 AQUI ESTÁ A CORREÇÃO

        if role:
            qry = qry.filter(func.lower(Pessoa.papel) == role.lower())

        rows = qry.group_by(
            Venda.pessoa_id,
            Pessoa.nome_pessoa
        ).all()

        labels = []
        counts = []
        totals = []
        ids = []

        for pid, nome, qtd, total in rows:
            ids.append(pid)
            labels.append(nome)
            counts.append(int(qtd))
            totals.append(float(total or 0))

        print("ROWS:", rows)
        print("LABELS:", labels)
        print("COUNTS:", counts)
        print("TOTALS:", totals)

        return jsonify({
            "date": hoje,
            "labels": labels,
            "counts": counts,
            "totals": totals,
            "ids": ids
        })

    finally:
        db.close()


@app.route('/teste', methods=['GET'])
@jwt_required()
def rota_teste():
    db_session = local_session()
    try:
        claims = get_jwt()
        id_usuario = claims['id_usuario']
        return jsonify({'sucesso': id_usuario}), 200
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        db_session.close()


@app.route('/pedido/status/<int:id_pedido>', methods=['PUT'])
def atualizar_status_pedido(id_pedido):
    try:
        db_session = local_session()

        pedido = db_session.get(Pedido, id_pedido)

        if not pedido:
            return jsonify({"error": "Pedido não encontrado"}), 404

        dados = request.get_json()

        novo_status = dados.get("status")

        if novo_status not in [1, 2]:
            return jsonify({"error": "Status inválido"}), 400

        pedido.status = novo_status
        db_session.commit()

        return jsonify({"success": "Status atualizado com sucesso"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5002)

# TESTE PUSH
