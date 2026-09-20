FROM node:20-alpine

WORKDIR /app

COPY package.json ./
# If package-lock exists it will be copied, else install directly
COPY package*.json ./

RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
