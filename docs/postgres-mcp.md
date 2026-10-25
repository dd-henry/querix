# PostgreSQL MCP no VS Code

O workspace configura o servidor `postgres` usando a imagem Docker `crystaldba/postgres-mcp` em modo `restricted`. O modo restrito limita as operações MCP a transações somente leitura.

## Configuração local

1. Garanta que o Docker esteja instalado e em execução.
2. Copie `.env.mcp.example` para `.env.mcp`.
3. Em `.env.mcp`, defina `DATABASE_URI` com uma URI PostgreSQL usando a conexão que o app já utiliza. Não compartilhe nem versione esse arquivo.
4. No VS Code, abra **Chat: Open Customizations** > **MCP Servers** e inicie/reinicie o servidor `postgres`.
5. Peça ao agente, por exemplo: “Use o MCP postgres para listar as tabelas e colunas do schema public. Não leia dados das tabelas.”

Se a senha tiver caracteres reservados de URI, faça URL-encoding antes de colocá-la em `DATABASE_URI`. Para bancos acessados via `localhost`, a imagem documenta o mapeamento do host para sua rede Docker.

O arquivo `.env.mcp` é ignorado pelo Git. O exemplo contém apenas valores fictícios. Uma conta PostgreSQL dedicada com permissões somente de leitura é preferível; o modo restrito do servidor é uma proteção adicional, não substitui permissões mínimas no banco.
