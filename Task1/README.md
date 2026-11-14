# Задание 1. Повышение безопасности

## Файлы

| Файл | Содержимое |
|------|-----------|
| `BionicPRO_C4_account-management.drawio`, `.png` | C4-схема управления учётными записями |
| `../frontend/src/App.tsx` | Вход через Authorization Code с PKCE (`pkceMethod: 'S256'`) |
| `../keycloak/realm-export.json` | Клиент `reports-frontend` требует PKCE S256, прямой обмен логина и пароля отключён |

## PKCE вместо Code Grant

В клиенте `reports-frontend` включён атрибут `pkce.code.challenge.method = S256`. Keycloak не принимает запрос кода без `code_challenge`, а при обмене кода проверяет `code_verifier`. Публичный клиент не хранит секрет, поэтому перехваченный код без `code_verifier` бесполезен. Прямой обмен логина и пароля (`directAccessGrantsEnabled`) и неявный поток выключены.

На стороне фронтенда `keycloak-js` получает `pkceMethod: 'S256'` и сам создаёт `code_verifier` и `code_challenge`.

## Схема

Диаграмма дорабатывает исходную C4 BionicPRO: светло-голубые контейнеры взяты из неё, тёмно-синие добавлены.

- Целевая схема: пользователь входит через BFF, он выполняет Authorization Code + PKCE и хранит access и refresh токены в Redis. Браузер получает только cookie сессии, токены IdP до фронтенда не доходят.
- Keycloak работает как брокер: каждая внешняя служба удостоверения страны подключается отдельной записью Identity Provider (OIDC, SAML или LDAP). Магазин и CRM входят через Keycloak по OIDC.
- Персональные и медицинские данные лежат в локальной БД страны и доступны только через Profile Service. В Keycloak хранятся только идентификаторы и привязка к внешнему IdP.

В коде репозитория реализована часть Задачи 2: PKCE во фронтенде и в Keycloak. BFF, Redis, Profile Service и подключение внешних IdP описаны на диаграмме как архитектурное решение и в коде не реализованы. Веб-приложение в этом репозитории получает токен через `keycloak-js` (в Задании 2 показана именно эта текущая реализация).

## Проверка

```bash
docker compose up -d keycloak_db keycloak
```

Затем в консоли администратора Keycloak (http://localhost:8080) в клиенте `reports-frontend` на вкладке Advanced виден Proof Key for Code Exchange = S256.
