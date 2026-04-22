FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

ARG API_ORIGIN=http://api:8000
ENV API_ORIGIN=${API_ORIGIN}

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]
