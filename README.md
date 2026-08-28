# GDD Studio

Plataforma pessoal para criar e organizar Game Design Documents com Streamlit e PostgreSQL/Neon. A aplicação inclui fundação, projetos, editor hierárquico do GDD e as Etapas 1 a 5 do sistema Personagens + Árvore Narrativa.

## O que já está pronto

- Aplicação Streamlit com roteamento oficial, URLs navegáveis e sidebar responsiva.
- Interface Liquid Glass discreta, com tokens reutilizáveis, temas claro/escuro e redução de movimento.
- Configuração segura por `.env`, sem credenciais no código ou no `session_state`.
- SQLAlchemy 2 com psycopg 3, pool pequeno, `pool_pre_ping` e sessões curtas por transação.
- Alembic com uma migration inicial reproduzível.
- Estados amigáveis para banco não configurado, indisponível ou desatualizado.
- Testes isolados de configuração, esquema, integridade, transações, navegação, estilos e inicialização do app.
- Criação e edição de projetos com todos os campos principais, validação e persistência real.
- Biblioteca com pesquisa, filtro por status, ordenação e paginação.
- Cards responsivos com upload de capa persistido no Neon, progresso, favoritos, arquivamento e restauração.
- Página individual do projeto com indicadores, metadados e ações seguras.
- Exclusão permanente protegida por confirmação com o nome do projeto.
- Todas as consultas e escritas filtradas pelo proprietário configurado do workspace.
- Template GDD Completo com 16 categorias e 129 seções organizadas.
- Categorias, grupos, páginas e subseções personalizadas sem limite fixo de profundidade.
- Editor Markdown com modos Editar/Visualizar, status e progresso automático.
- Autosave ao pausar/sair do campo, botão Salvar agora e controle otimista de revisão.
- Ordenação segura por botões Subir/Descer e exclusão em cascata confirmada.
- Biblioteca de personagens por projeto com pesquisa, filtro por papel, ordenação e cards responsivos.
- Ficha completa com identificação, visão geral, história, personalidade, objetivos, arco narrativo, aparência e gameplay.
- CRUD de personagens isolado por proprietário e projeto, nomes únicos e controle otimista de revisão.
- Estrutura narrativa com capítulos, cenas, resumos e conteúdo em Markdown.
- Ordenação de capítulos e cenas com linha temporal global recalculada automaticamente.
- Movimentação de cenas entre capítulos e exclusão em cascata protegida por confirmação.
- Seleção pesquisável de personagens dentro de cada cena, persistida como vínculo many-to-many.
- Papel e notas opcionais por participação, sem duplicação de personagem ou perda de metadados.
- Aparições, primeira/última cena, capítulos e linha narrativa calculados automaticamente na ficha.
- Relações direcionais entre personagens com tipo predefinido ou personalizado, estado, intensidade e descrição.
- Relações iniciadas e recebidas exibidas separadamente, com edição, exclusão e integridade em cascata.
- Mapa Narrativo interativo derivado dos dados reais de projeto, capítulos, cenas, aparições e relações.
- Nós móveis, pan, zoom, destaque de conexões, legenda e painel detalhado com acesso às entidades.

O editor do GDD e os módulos seguintes permanecem separados para as próximas etapas, sem dados mockados.

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
GDD_OWNER_NAME=Criador
GDD_OWNER_EMAIL=creator@gdd.local
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
GDD_OWNER_NAME = "Criador"
GDD_OWNER_EMAIL = "creator@gdd.local"
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
services/project_service.py # CRUD e consultas de projetos filtradas pelo dono
services/gdd_service.py     # hierarquia, editor, autosave e ordenação
services/character_service.py # CRUD e consultas de personagens
services/narrative_service.py # capítulos, cenas e ordem narrativa
services/appearance_service.py # elenco das cenas e aparições calculadas
services/relationship_service.py # grafo direcional entre personagens
services/narrative_map_service.py # projeção relacional para o mapa interativo
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
- `characters` (fichas completas vinculadas ao projeto)
- `chapters` e `scenes` (estrutura e ordem narrativa)
- `scene_characters` (vínculos de aparição personagem–cena)
- `character_relationships` (relações direcionais personagem–personagem)

Os IDs são UUIDs. Conteúdos grandes são `Text` e carregados sob demanda. Snapshots usam JSONB no PostgreSQL. Seções, notas e itens de roadmap possuem revisão otimista para preparar o autosave sem sobrescritas silenciosas.

## Limitações atuais

- Ainda não há autenticação. Não publique o app sem proteção externa até a camada de usuários estar implementada.
- Até lá, o banco não impede sozinho uma associação de tag entre proprietários diferentes; os serviços multiusuário deverão validar ownership em toda escrita, com constraints/RLS em uma migration futura.
- Capas PNG, JPG e WebP de até 3 MB são armazenadas diretamente no Neon.
- Retratos de personagens usam URL pública; upload direto ainda não possui armazenamento de objetos.
- Pesquisa, filtros e modos de foco do mapa pertencem à próxima etapa do novo sistema.
- O autosave ocorre quando o Streamlit sincroniza o campo — ao pausar/sair dele ou usar Ctrl+Enter — evitando uma escrita por tecla.
- Não há dados demonstrativos nem persistência local alternativa.
- A conexão real e a migration no Neon precisam de credenciais fornecidas por você.

## Próxima etapa do sistema narrativo

A **Etapa 6 — Filtros e foco** adicionará pesquisa, filtros por categoria, foco em personagem/cena e destaque de caminhos.
