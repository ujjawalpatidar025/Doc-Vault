FROM node:22-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy project files
COPY . .

EXPOSE 3000

# Vite dev server (host/port set in vite.config.js)
CMD ["npm", "run", "dev"]
