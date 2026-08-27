# GDD Studio

Fundação de uma plataforma pessoal para criar e organizar Game Design Documents com Streamlit e PostgreSQL/Neon. Esta entrega cobre somente a **Etapa 1** do plano: arquitetura, configuração, persistência, modelos, migrations, design system e navegação.

## O que já está pronto

- Aplicação Streamlit com roteamento oficial, URLs navegáveis e sidebar responsiva.
- Interface Liquid Glass discreta, com tokens reutilizáveis, temas claro/escuro e redução de movimento.
- Configuração segura por `.env`, sem credenciais no código ou no `session_state`.
- SQLAlchemy 2 com psycopg 3, pool pequeno, `pool_pre_ping` e sessões curtas por transação.
- Alembic com uma migration inicial reproduzível.
- Estados amigáveis para banco não configurado, indisponível ou desatualizado.
- Testes isolados de configuração, esquema, integridade, transações, navegação, estilos e inicialização do app.

As telas de projetos, editor e demais recursos aparecem apenas como rotas preparadas. Elas serão implementadas nas etapas correspondentes, sem dados mockados.

## Requisitos

- Python 3.11 ou superior (3.12 recomendado)
- Uma conta e um projeto no [Neon](https://neon.tech/)

## Desenvolvimento local

Crie e ative um ambiente virtual:

```bash
python -m venv .venv
```

No Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

No macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Para executar também testes, cobertura e lint, instale as dependências de desenvolvimento:

```bash
pip install -r requirements-dev.txt
```

Se você usa `uv`, a alternativa é:

```bash
uv venv --python 3.12
uv pip install -r requirements.txt
```

## Configuração do Neon

1. Crie um projeto no Neon.
2. Copie `.env.example` para `.env`.
3. Cole a connection string pooled do Neon em `DATABASE_URL`.
4. Opcionalmente, coloque a connection string direta em `DATABASE_DIRECT_URL`; ela é preferida pelo Alembic.
5. Mantenha `sslmode=require` na URL ou em `DATABASE_SSLMODE`.

Exemplo de formato (use os valores reais fornecidos pelo Neon):

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST-pooler.neon.tech/DATABASE?sslmode=require
DATABASE_DIRECT_URL=postgresql+psycopg://USER:PASSWORD@HOST.neon.tech/DATABASE?sslmode=require
```

Nunca versione `.env` ou `.streamlit/secrets.toml`.

## Criar ou atualizar as tabelas

Execute a migration versionada:

```bash
python -m scripts.init_db
```

Confira a conexão e a revisão:

```bash
python -m scripts.check_database
```

O app não executa DDL em cada rerun e não cria fallback SQLite. O Neon continua sendo a única fonte permanente. SQLite existe somente nos testes rápidos em memória.

## Executar

```bash
streamlit run app.py
```

Abra `http://localhost:8501`. Sem `DATABASE_URL`, o app inicia normalmente e mostra a configuração necessária sem traceback ou credenciais.

## Testes e qualidade

```bash
pytest
ruff check .
ruff format --check .
```

Uma validação PostgreSQL/Neon real depende de uma URL de banco fornecida no ambiente. Os testes rápidos não acessam sua conta nem criam arquivos persistentes.

## Deploy no Streamlit Community Cloud

1. Publique o projeto em um repositório privado.
2. Crie o app apontando para `app.py`.
3. Em **App settings → Secrets**, adicione as variáveis como TOML:

```toml
DATABASE_URL = "postgresql+psycopg://..."
DATABASE_DIRECT_URL = "postgresql+psycopg://..."
```

4. Execute a migration contra o Neon antes de liberar o app.

As chaves de nível raiz dos secrets ficam disponíveis como variáveis de ambiente para a aplicação. Não inclua `.env` no deploy.

## Estrutura

```text
app.py                    # entrypoint e barreira central de banco
components/               # shell, navegação, cards e feedback
config/                   # leitura e validação do ambiente
models/                   # modelos SQLAlchemy
services/database.py      # engine, sessões, health check e migration
pages/                    # rotas pequenas e independentes
styles/                   # design system CSS separado
migrations/               # evolução versionada do PostgreSQL
scripts/                  # comandos operacionais seguros
tests/                    # testes rápidos isolados
```

## Estrutura inicial do banco

- `users`
- `projects`
- `gdd_sections` (hierarquia via `parent_id`)
- `notes`
- `ideas`
- `project_references`
- `tags`
- `project_tags`, `section_tags`, `note_tags`, `idea_tags`, `reference_tags`
- `project_versions`
- `roadmap_items`

Os IDs são UUIDs. Conteúdos grandes são `Text` e carregados sob demanda. Snapshots usam JSONB no PostgreSQL. Seções, notas e itens de roadmap possuem revisão otimista para preparar o autosave sem sobrescritas silenciosas.

## Limitações atuais

- Ainda não há autenticação. Não publique o app sem proteção externa até a camada de usuários estar implementada.
- Até lá, o banco não impede sozinho uma associação de tag entre proprietários diferentes; os serviços multiusuário deverão validar ownership em toda escrita, com constraints/RLS em uma migration futura.
- Não há CRUD de projetos; isso pertence à Etapa 2.
- O editor e o autosave pertencem à Etapa 3.
- Não há dados demonstrativos nem persistência local alternativa.
- A conexão real e a migration no Neon precisam de credenciais fornecidas por você.

## Próxima etapa

A **Etapa 2 — Projetos** deve implementar serviços e telas para criar, editar, listar, favoritar, arquivar e excluir projetos, incluindo a página individual do jogo. Cada consulta deverá sempre ser filtrada pelo proprietário.
