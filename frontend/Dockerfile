FROM node:20-alpine

WORKDIR /app

# Install deps
COPY package.json package-lock.json* ./
RUN npm install

# Copy source
COPY . .

# Dev server with hot reload
CMD ["npm", "run", "dev"]
