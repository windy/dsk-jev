# Security

This is experimental software; v0.1.x is the currently maintained release line.

Never include credentials or private customer data in public issues. Report vulnerabilities through GitHub's private vulnerability reporting feature if enabled on this repository; otherwise open an issue asking the maintainer for a private reporting channel without disclosing exploit details.

Use a unique PROXY_API_KEY, keep DEEPSEEK_API_KEY on the server, and bind to localhost or put the service behind an authenticated TLS gateway with rate limits. The service has no tenant isolation or built-in rate limiting. Requests are sent to your configured upstream; remote image URLs are fetched by that provider. Do not submit secrets in state, images or question descriptions.

Usage records omit request inputs, but remain operational data. Limit their filesystem access and retention. They are not a transactionally durable billing ledger. Never commit .env files, production logs or real keys.
