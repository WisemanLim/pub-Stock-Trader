# Rust workspace build — context must be repo root (docker-compose: context: .)
FROM rust:1 AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock* ./
COPY core/risk-engine ./core/risk-engine
COPY apps/tui        ./apps/tui
RUN cargo build --release -p risk-engine

FROM debian:bookworm-slim
COPY --from=build /src/target/release/risk-engine /app/risk-engine
EXPOSE 3001
CMD ["/app/risk-engine"]
