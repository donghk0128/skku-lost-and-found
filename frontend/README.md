# Welcome to your Expo app 👋

This is an [Expo](https://expo.dev) project created with [`create-expo-app`](https://www.npmjs.com/package/create-expo-app).

## Get started

1. Install dependencies

   ```bash
   npm install
   ```

2. Start the app

   ```bash
   npx expo start
   ```

In the output, you'll find options to open the app in a

- [development build](https://docs.expo.dev/develop/development-builds/introduction/)
- [Android emulator](https://docs.expo.dev/workflow/android-studio-emulator/)
- [iOS simulator](https://docs.expo.dev/workflow/ios-simulator/)
- [Expo Go](https://expo.dev/go), a limited sandbox for trying out app development with Expo

You can start developing by editing the files inside the **app** directory. This project uses [file-based routing](https://docs.expo.dev/router/introduction).

## Get a fresh project

When you're ready, run:

```bash
npm run reset-project
```

This command will move the starter code to the **app-example** directory and create a blank **app** directory where you can start developing.

### Other setup steps

- To set up ESLint for linting, run `npx expo lint`, or follow our guide on ["Using ESLint and Prettier"](https://docs.expo.dev/guides/using-eslint/)
- If you'd like to set up unit testing, follow our guide on ["Unit Testing with Jest"](https://docs.expo.dev/develop/unit-testing/)
- Learn more about the TypeScript setup in this template in our guide on ["Using TypeScript"](https://docs.expo.dev/guides/typescript/)

## Learn more

To learn more about developing your project with Expo, look at the following resources:

- [Expo documentation](https://docs.expo.dev/): Learn fundamentals, or go into advanced topics with our [guides](https://docs.expo.dev/guides).
- [Learn Expo tutorial](https://docs.expo.dev/tutorial/introduction/): Follow a step-by-step tutorial where you'll create a project that runs on Android, iOS, and the web.

## Join the community

Join our community of developers creating universal apps.

- [Expo on GitHub](https://github.com/expo/expo): View our open source platform and contribute.
- [Discord community](https://chat.expo.dev): Chat with Expo users and ask questions.

## API 주소 설정

로컬 설정은 `.env.local`에서 관리합니다. 모든 인증 API는 아래 주소를 공통으로 사용합니다.

```dotenv
EXPO_PUBLIC_API_URL=http://localhost:8000/api/v1
```

서버를 변경할 때는 이 값만 수정하고 Expo를 재시작하세요. 새 환경에서는 `.env.example`을 `.env.local`로 복사합니다.

- 웹 / iOS 시뮬레이터: `http://localhost:8000/api/v1`
- Android 에뮬레이터: `http://10.0.2.2:8000/api/v1`
- 실제 휴대폰: 같은 Wi-Fi에 연결된 개발 컴퓨터의 LAN IP를 사용합니다(예: `http://192.168.0.10:8000/api/v1`).

`.env.local`은 Git에 포함되지 않습니다. `EXPO_PUBLIC_` 변수는 앱에 공개되므로 비밀 키를 넣지 마세요.
