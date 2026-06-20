import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors();
  const port = process.env.BFF_PORT ?? 3002;
  await app.listen(port);
  // eslint-disable-next-line no-console
  console.log(`bff listening on :${port}`);
}
bootstrap();
