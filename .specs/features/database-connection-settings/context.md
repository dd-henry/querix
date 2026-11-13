# Configuração da conexão do banco consultado Context

**Gathered:** 2026-11-12
**Spec:** `.specs/features/database-connection-settings/spec.md`
**Status:** Ready for design

## Feature Boundary

A entrega adiciona uma tela de Configurações para um admin definir uma única
connection string PostgreSQL global para o banco consultado pelo Ask-SQL. A
aplicação mantém uma conexão interna separada para autenticação e persistência.

## Implementation Decisions

### Escopo da conexão

- A configuração da tela é do banco-alvo consultado pelo Ask-SQL.
- `DATABASE_URL` continua sendo a conexão interna da aplicação.

### Proprietário e persistência

- Somente perfis com papel `admin` podem consultar o status ou salvar a conexão.
- A configuração vale para todos os usuários aprovados.
- A credencial fica cifrada no servidor e não é retornada após o salvamento.

### Entrada e ativação

- A tela recebe somente uma connection string completa.
- O servidor executa `SELECT 1` antes de persistir.
- Uma falha de teste não substitui a configuração anterior.

## Agent's Discretion

- Organização visual da tela dentro do painel existente de Configurações.
- Nome interno da tabela e dos módulos, desde que preserve o contrato da
  especificação e as convenções do repositório.
- Mensagens de carregamento e sucesso em português, seguindo os componentes
  existentes.

## Declined / Undiscussed Gray Areas → Assumptions

- Rotação independente da chave de cifragem não faz parte desta entrega; a chave
  deriva de `SESSION_SECRET`, que já é segredo obrigatório do servidor.
- O recurso não adiciona múltiplos perfis de conexão, seleção de ambiente ou
  histórico de credenciais.

## Specific References

O usuário confirmou: `separate_target`, `admin_global` e
`connection_string_only`.

## Deferred Ideas

- Configuração por usuário.
- Suporte a múltiplos bancos-alvo e seleção por conversa.
