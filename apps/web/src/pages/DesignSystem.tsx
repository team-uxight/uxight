import { useState } from 'react'
import { ArrowLeft, Check, CircleAlert, CircleCheck, Info, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Chip } from '@/components/ui/chip'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

const filters = ['전체', 'Navigation', 'Discoverability', 'Task Failure']

export default function DesignSystem() {
  const [selectedFilter, setSelectedFilter] = useState('전체')
  const [confirmed, setConfirmed] = useState(false)

  return (
    <main className="min-h-screen bg-background px-5 py-10 text-foreground sm:px-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-10 flex flex-wrap items-start justify-between gap-5">
          <div>
            <Link className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground" to="/dashboard">
              <ArrowLeft aria-hidden="true" size={16} />
              UXight로 돌아가기
            </Link>
            <div className="flex items-center gap-2 text-sm font-semibold text-primary">
              <Sparkles aria-hidden="true" size={16} />
              UI foundations · v1
            </div>
            <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">디자인 시스템</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
              테마 토큰을 기반으로 재사용하는 공통 UI 컴포넌트입니다. 아래 칩과 확인 다이얼로그를 직접 조작해 볼 수 있어요.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            <Badge variant="success"><CircleCheck aria-hidden="true" /> 테마 적용</Badge>
            <Badge variant="info"><Info aria-hidden="true" /> shadcn/ui 스타일</Badge>
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>01 · 배지 Badge</CardTitle>
              <CardDescription>상태와 심각도처럼 짧은 정보를 표시합니다.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Badge>기본</Badge>
              <Badge variant="secondary">보조</Badge>
              <Badge variant="success"><Check aria-hidden="true" /> 완료</Badge>
              <Badge variant="warning"><CircleAlert aria-hidden="true" /> 확인 필요</Badge>
              <Badge variant="destructive">오류</Badge>
              <Badge variant="info">정보</Badge>
              <Badge variant="outline">초안</Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>02 · 칩 Chip</CardTitle>
              <CardDescription>필터나 태그처럼 선택 상태를 토글합니다.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {filters.map((filter) => (
                <Chip
                  key={filter}
                  variant="outline"
                  pressed={selectedFilter === filter}
                  onPressedChange={(pressed) => {
                    if (pressed) setSelectedFilter(filter)
                  }}
                  aria-label={`${filter} 필터`}
                >
                  {filter}
                </Chip>
              ))}
            </CardContent>
            <CardFooter className="text-sm text-muted-foreground">
              선택한 필터: <span className="ml-1 font-semibold text-foreground">{selectedFilter}</span>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>03 · 카드 Card</CardTitle>
              <CardDescription>관련 정보와 액션을 하나의 표면에 묶습니다.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border bg-background p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">학사 안내 메뉴 시인성 부족</h3>
                    <p className="mt-1 text-sm text-muted-foreground">Novice 페르소나 3명에게서 반복 관찰</p>
                  </div>
                  <Badge variant="warning">중요도 높음</Badge>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Badge variant="secondary">Discoverability</Badge>
                  <Badge variant="outline">2분 전</Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>04 · 확인 다이얼로그</CardTitle>
              <CardDescription>취소하거나 확인할 수 있는 중요 작업에 사용합니다.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-3">
              <ConfirmDialog
                title="개선안을 승인할까요?"
                description="승인 후 개선안이 적용된 것으로 기록됩니다. 이 데모에서는 실제 사이트나 서버 데이터가 변경되지 않습니다."
                confirmLabel="승인"
                onConfirm={() => setConfirmed(true)}
              >
                <button className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40" type="button">
                  다이얼로그 열기
                </button>
              </ConfirmDialog>
              <ConfirmDialog
                title="이 작업을 삭제할까요?"
                description="삭제 후에는 목록에서 사라집니다. 이 데모에서는 실제 데이터가 삭제되지 않습니다."
                confirmLabel="삭제"
                destructive
                onConfirm={() => setConfirmed(true)}
              >
                <button className="inline-flex h-10 items-center justify-center rounded-lg border border-border bg-background px-4 text-sm font-semibold transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40" type="button">
                  삭제 확인 예시
                </button>
              </ConfirmDialog>
            </CardContent>
            {confirmed && (
              <CardFooter role="status" className="gap-2 text-sm font-medium text-success">
                <CircleCheck aria-hidden="true" size={16} />
                확인 동작을 테스트했어요.
                <button className="ml-auto underline underline-offset-4" onClick={() => setConfirmed(false)} type="button">
                  초기화
                </button>
              </CardFooter>
            )}
          </Card>
        </div>

        <footer className="mt-8 rounded-xl border border-dashed border-border bg-card/70 p-5 text-sm leading-6 text-muted-foreground">
          색상, 글꼴, 반경 등은 <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">src/styles/tokens.css</code>의 테마 변수에서 관리합니다.
          컴포넌트 소스는 <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">src/components/ui</code>에 있습니다.
        </footer>
      </div>
    </main>
  )
}
