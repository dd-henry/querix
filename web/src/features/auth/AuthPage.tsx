import { useState, type FormEvent, type InputHTMLAttributes } from "react";

import { ApiError } from "../../api/client";
import { useAuth } from "../../app/AuthProvider";

const SIGNUP_SUCCESS_MESSAGE =
  "Cadastro recebido. Confirme seu email e aguarde a aprovação de um admin.";

type AuthMode = "login" | "signup" | "change";
type ActiveOperation = AuthMode | null;
type Feedback = {
  kind: "error" | "success";
  message: string;
};

function PasswordInput({
  description,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { description: string }) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="password-field">
      <input {...props} type={visible ? "text" : "password"} />
      <button
        type="button"
        className="password-toggle"
        aria-label={`${visible ? "Ocultar" : "Mostrar"} ${description}`}
        aria-pressed={visible}
        aria-controls={props.id}
        onClick={() => setVisible((previous) => !previous)}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          aria-hidden="true">
          <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
          {visible ? <path d="M4 4 20 20" /> : null}
        </svg>
      </button>
    </div>
  );
}

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

function validateNewPassword(
  currentPassword: string,
  newPassword: string,
  confirmation: string,
): string | undefined {
  if (newPassword.length < 8) {
    return "A senha deve ter pelo menos 8 caracteres.";
  }
  if (newPassword !== confirmation) {
    return "As senhas não conferem.";
  }
  if (newPassword === currentPassword) {
    return "A nova senha deve ser diferente da senha temporária.";
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
  const [newPassword, setNewPassword] = useState("");
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
      if (error instanceof ApiError && error.code === "password_change_required") {
        setNewPassword("");
        setPasswordConfirmation("");
        setMode("change");
        setFeedback({ kind: "success", message: error.message });
        return;
      }
      setPassword("");
      setFeedback({
        kind: "error",
        message: `Não foi possível entrar: ${errorMessage(error)}`,
      });
    } finally {
      setActiveOperation(null);
    }
  }

  async function submitChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (activeOperation) {
      return;
    }

    const validationMessage = validateNewPassword(
      password,
      newPassword,
      passwordConfirmation,
    );
    if (validationMessage) {
      setFeedback({ kind: "error", message: validationMessage });
      return;
    }

    setFeedback(null);
    setActiveOperation("change");
    try {
      await auth.changePassword({
        email: email.trim(),
        current_password: password,
        new_password: newPassword,
        new_password_confirmation: passwordConfirmation,
      });
    } catch (error: unknown) {
      setFeedback({
        kind: "error",
        message: `Não foi possível alterar a senha: ${errorMessage(error)}`,
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
          {mode === "login"
            ? "Entrar para continuar"
            : mode === "change"
              ? "Defina uma nova senha"
              : "Criar sua conta"}
        </h1>
        {mode === "change" ? null : (
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
        )}

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
            <PasswordInput
              key="login-password"
              id="login-password"
              name="password"
              description="senha"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button type="submit" disabled={activeOperation === "login"}>
              {activeOperation === "login" ? "Entrando..." : "Entrar"}
            </button>
          </form>
        ) : mode === "change" ? (
          <form
            className="auth-form"
            aria-busy={activeOperation === "change"}
            noValidate
            onSubmit={submitChangePassword}
          >
            <label htmlFor="change-new-password">Nova senha</label>
            <PasswordInput
              key="change-new-password"
              id="change-new-password"
              name="new_password"
              description="nova senha"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <label htmlFor="change-password-confirmation">
              Confirmar nova senha
            </label>
            <PasswordInput
              key="change-password-confirmation"
              id="change-password-confirmation"
              name="new_password_confirmation"
              description="confirmar nova senha"
              autoComplete="new-password"
              value={passwordConfirmation}
              onChange={(event) => setPasswordConfirmation(event.target.value)}
            />
            <button type="submit" disabled={activeOperation === "change"}>
              {activeOperation === "change" ? "Salvando..." : "Salvar e entrar"}
            </button>
            <button
              type="button"
              disabled={activeOperation !== null}
              onClick={() => {
                setPassword("");
                changeMode("login");
              }}
            >
              Voltar
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
            <PasswordInput
              key="signup-password"
              id="signup-password"
              name="password"
              description="senha"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <label htmlFor="signup-password-confirmation">
              Confirmar senha
            </label>
            <PasswordInput
              key="signup-password-confirmation"
              id="signup-password-confirmation"
              name="password_confirmation"
              description="confirmar senha"
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
