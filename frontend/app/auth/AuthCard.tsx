"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";

import {
  loginUser,
  registerUser,
  type UserRole,
} from "../../services/api";

export default function AuthCard() {
  const router = useRouter();
  const [isLogin, setIsLogin] = useState(true);
  const [role, setRole] = useState<UserRole>("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [usn, setUsn] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const toggleMode = () => {
    setIsLogin((current) => !current);
    setErrorMsg("");
    setPassword("");
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");

    try {
      if (isLogin) {
        const result = await loginUser(email, password);
        localStorage.setItem("userToken", result.token);
        localStorage.setItem("userRole", result.user.role);
        router.replace(
          result.user.role === "teacher" ? "/teacher" : `/student/${result.user.userId}`,
        );
        return;
      }

      const result = await registerUser({
        email,
        password,
        fullName,
        role,
        ...(role === "student" ? { usn } : {}),
      });
      localStorage.setItem("userToken", result.token);
      localStorage.setItem("userRole", result.user.role);
      router.replace(
        result.user.role === "teacher" ? "/teacher" : `/student/${result.user.userId}`,
      );
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Authentication process failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="authBox">
      <div className="flex items-center justify-center gap-2.5 mb-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-600 text-white font-black shadow-md shadow-blue-500/20">
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
          </svg>
        </div>
        <span className="text-2xl sm:text-3xl font-black tracking-tight">
          <span className="text-blue-600">Learn</span>
          <span className="text-slate-900">Pulse</span>
        </span>
      </div>
      <div className="authHeader">
        <h1>{isLogin ? "Welcome Back" : "Create Account"}</h1>
        <p>{isLogin ? "Sign in to your LearnPulse workspace" : "Register your academic account"}</p>
      </div>

      {errorMsg && <div className="alertBanner">⚠️ {errorMsg}</div>}

      <form onSubmit={handleFormSubmit} className="authForm">
        {!isLogin && (
          <div className="formGroup">
            <label htmlFor="full-name">Full Name</label>
            <input
              id="full-name"
              type="text"
              required
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Alex Mercer"
            />
          </div>
        )}

        {!isLogin && role === "student" && (
          <div className="formGroup">
            <label htmlFor="student-usn">Student USN</label>
            <input
              id="student-usn"
              type="text"
              required
              minLength={4}
              maxLength={32}
              autoComplete="off"
              value={usn}
              onChange={(e) => setUsn(e.target.value)}
              placeholder="e.g. 1AB23CS001"
            />
            <p className="formHint">Use 4–32 letters, numbers, hyphens, or slashes.</p>
          </div>
        )}

        <div className="formGroup">
          <label htmlFor="email">Email Address</label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@university.edu"
          />
        </div>

        <div className="formGroup">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            autoComplete={isLogin ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
        </div>

        {!isLogin && (
          <div className="formGroup">
            <span className="formLabel">Account Type</span>
            <div className="roleGrid">
              <button
                type="button"
                aria-pressed={role === "student"}
                onClick={() => setRole("student")}
                className={`roleBtn ${role === "student" ? "roleBtnActive" : ""}`}
              >
                🎓 Student
              </button>
              <button
                type="button"
                aria-pressed={role === "teacher"}
                onClick={() => setRole("teacher")}
                className={`roleBtn ${role === "teacher" ? "roleBtnActive" : ""}`}
              >
                🏫 Faculty
              </button>
            </div>
          </div>
        )}

        <button type="submit" disabled={loading} className="btnMain">
          {loading ? "Verifying..." : isLogin ? "Sign In" : "Register"}
        </button>
      </form>

      <p className="modePrompt">
        {isLogin ? "New to LearnPulse?" : "Already have an account?"}
        <button
          type="button"
          onClick={toggleMode}
          disabled={loading}
          className="toggleLink"
        >
          {isLogin ? "Create an account" : "Sign in"}
        </button>
      </p>
    </div>
  );
}
