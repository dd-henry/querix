import { useState, type FormEvent } from "react";

import { useAuth } from "../../app/AuthProvider";

const SIGNUP_SUCCESS_MESSAGE =
  "Cadastro recebido. Confirme seu email e aguarde a aprovação de um admin.";

type AuthMode = "login" | "signup";
type ActiveOperation = AuthMode | null;
type Feedback = {
  kind: "error" | "success";
  message: string;
};

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Tente novamente.";
}

function validateLogin(email: string, password: string): string | undefined {
  if (!email.trim() || !password) {
    return "Informe email e senha.";
  }
  return undefined;
}

function validateSignup(
  name: string,
  email: string,
  password: string,
  passwordConfirmation: string,
): string | undefined {
  if (!name.trim() || !email.trim()) {
    return "Informe nome e email.";
  }
  if (password.length < 8) {
    return "A senha deve ter pelo menos 8 caracteres.";
  }
  if (password !== passwordConfirmation) {
    return "As senhas não conferem.";
  }
  return undefined;
}

export function AuthPage() {
  const auth = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [activeOperation, setActiveOperation] =
    useState<ActiveOperation>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  function changeMode(nextMode: AuthMode) {
    if (activeOperation) {
      return;
    }
    setMode(nextMode);
    setFeedback(null);
  }

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (activeOperation) {
      return;
    }

    const validationMessage = validateLogin(email, password);
    if (validationMessage) {
      setFeedback({ kind: "error", message: validationMessage });
      return;
    }

    setFeedback(null);
    setActiveOperation("login");
    try {
      await auth.login({ email: email.trim(), password });
    } catch (error: unknown) {
      setPassword("");
      setFeedback({
        kind: "error",
        message: `Não foi possível entrar: ${errorMessage(error)}`,
      });
    } finally {
      setActiveOperation(null);
    }
  }

  async function submitSignup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (activeOperation) {
      return;
    }

    const validationMessage = validateSignup(
      name,
      email,
      password,
      passwordConfirmation,
    );
    if (validationMessage) {
      setFeedback({ kind: "error", message: validationMessage });
      return;
    }

    setFeedback(null);
    setActiveOperation("signup");
    try {
      const response = await auth.signup({
        name: name.trim(),
        email: email.trim(),
        password,
        password_confirmation: passwordConfirmation,
      });
      setFeedback({
        kind: "success",
        message: response?.message || SIGNUP_SUCCESS_MESSAGE,
      });
    } catch (error: unknown) {
      setFeedback({
        kind: "error",
        message: `Não foi possível criar conta: ${errorMessage(error)}`,
      });
    } finally {
      setActiveOperation(null);
    }
  }

  return (
    <main className="app-shell">
      <section className="welcome-card" aria-labelledby="auth-title">
        <p className="eyebrow">Ask SQL</p>
        <h1 id="auth-title">
          {mode === "login" ? "Entrar para continuar" : "Criar sua conta"}
        </h1>
        <div className="auth-tabs" role="tablist" aria-label="Autenticação">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            disabled={activeOperation !== null}
            onClick={() => changeMode("login")}
          >
            Entrar
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "signup"}
            disabled={activeOperation !== null}
            onClick={() => changeMode("signup")}
          >
            Criar conta
          </button>
        </div>

        {mode === "login" ? (
          <form
            className="auth-form"
            aria-busy={activeOperation === "login"}
            noValidate
            onSubmit={submitLogin}
          >
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <label htmlFor="login-password">Senha</label>
            <input
              id="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button type="submit" disabled={activeOperation === "login"}>
              {activeOperation === "login" ? "Entrando..." : "Entrar"}
            </button>
          </form>
        ) : (
          <form
            className="auth-form"
            aria-busy={activeOperation === "signup"}
            noValidate
            onSubmit={submitSignup}
          >
            <label htmlFor="signup-name">Nome completo</label>
            <input
              id="signup-name"
              name="name"
              type="text"
              autoComplete="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <label htmlFor="signup-email">Email</label>
            <input
              id="signup-email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <label htmlFor="signup-password">Senha</label>
            <input
              id="signup-password"
              name="password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <label htmlFor="signup-password-confirmation">
              Confirmar senha
            </label>
            <input
              id="signup-password-confirmation"
              name="password_confirmation"
              type="password"
              autoComplete="new-password"
              value={passwordConfirmation}
              onChange={(event) => setPasswordConfirmation(event.target.value)}
            />
            <button type="submit" disabled={activeOperation === "signup"}>
              {activeOperation === "signup"
                ? "Criando conta..."
                : "Solicitar acesso"}
            </button>
          </form>
        )}

        {feedback ? (
          <p
            className={`auth-feedback auth-feedback--${feedback.kind}`}
            role={feedback.kind === "error" ? "alert" : "status"}
          >
            {feedback.message}
          </p>
        ) : null}
      </section>
    </main>
  );
}
