"use client";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { TokenAuthTab } from "./token-auth-tab";
import { OAuthTab } from "./oauth-tab";

interface AuthTabsProps {
  token: string | null;
}

export function AuthTabs({ token }: AuthTabsProps) {
  return (
    <Tabs defaultValue="token">
      <TabsList variant="line">
        <TabsTrigger value="token">Token Auth</TabsTrigger>
        <TabsTrigger value="oauth">OAuth (Claude Desktop)</TabsTrigger>
      </TabsList>
      <TabsContent value="token">
        <TokenAuthTab token={token} />
      </TabsContent>
      <TabsContent value="oauth">
        <OAuthTab />
      </TabsContent>
    </Tabs>
  );
}
