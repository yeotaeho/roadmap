"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Search, ChevronLeft, ChevronRight, Share2, Printer, ChevronDown, AlignJustify } from 'lucide-react';
import { getUserName } from '@/utils/tokenStorage';
import { useAuth } from '@/hooks/useStore';
import { getCurrentUser } from '@/lib/api/user';

// Mock Data (가상 데이터)
const NAV_LINKS = ['트랜드 분석', '챗', '프레스센터', '뉴스룸소개'];
const HEADER_LINKS = ['전체 기사', '경제', '정치', '사회', '문화', '국제/세계', 'IT/과학', '스포츠', '연예'];

// API에서 가져올 뉴스 기사 타입
interface NewsArticle {
    type: string;
    title: string;
    date?: string;
    image: string;
    link?: string;
    description?: string;
}
const MORE_STORIES = [
    { type: '뉴스룸픽', title: '삼성전자, 삼성 페이와 모빌리티 서비스 제휴', image: 'https://placehold.co/400x250/F2F2F2/333333?text=STORY+1' },
    { type: '디바이스', title: 'QLED TV, 2026년에 더욱 완벽한 모습으로 업그레이드되어 돌아온다', image: 'https://placehold.co/400x250/F2F2F2/333333?text=STORY+2' },
    { type: '테크놀로지', title: '삼성전자, 희귀 난치병 어린이 돕기 위한 캠페인', image: 'https://placehold.co/400x250/F2F2F2/333333?text=STORY+3' },
    { type: '캠페인', title: '모두가 인정하는 갤럭시 Z 플립 2 드라이브 투어 현장', image: 'https://placehold.co/400x250/F2F2F2/333333?text=STORY+4' },
];
const DISCOVERY_ITEMS = [
    { title: '갤럭시 Z 폴드 6 | Z 플립 7', subtitle: '혁신 그 이상', image: 'https://placehold.co/400x280/F2F2F2/333333?text=GALAXY+Z' },
    { title: '6G', subtitle: '미래를 향한 연결', image: 'https://placehold.co/400x280/F2F2F2/333333?text=6G' },
    { title: 'Bespoke AI', subtitle: '맞춤형 라이프스타일', image: 'https://placehold.co/400x280/F2F2F2/333333?text=BESPOKE+AI' },
    { title: 'Vision AI', subtitle: '새로운 시야', image: 'https://placehold.co/400x280/F2F2F2/333333?text=VISION+AI' },
];
const MEDIA_HIGHLIGHTS = [
    { title: 'IFA 2025', image: 'https://placehold.co/400x280/1A1A1A/FFFFFF?text=IFA+2025' },
    { title: '국내 사업장', image: 'https://placehold.co/400x280/1A1A1A/FFFFFF?text=KOREA' },
    { title: '갤럭시 Z 폴드 2 | Z 플립 7', image: 'https://placehold.co/400x280/1A1A1A/FFFFFF?text=GALAXY' },
    { title: 'CES 2025', image: 'https://placehold.co/400x280/1A1A1A/FFFFFF?text=CES+2025' },
    { title: '삼성전자 비전', image: 'https://placehold.co/400x280/1A1A1A/FFFFFF?text=VISION' },
    { title: '갤럭시 S25 시리즈', image: 'https://placehold.co/400x280/1A1A1A/FFFFFF?text=GALAXY+S25' },
];

// Types
interface Article {
    type: string;
    title: string;
    date?: string;
    image: string;
}

interface Item {
    title: string;
    subtitle?: string;
    image: string;
}

// Reusable Card Component (재사용 가능한 카드 컴포넌트)
const ArticleCard = ({ article, large = false }: { article: Article; large?: boolean }) => (
    <div className={`flex flex-col rounded-lg overflow-hidden ${large ? 'col-span-1 sm:col-span-2 md:col-span-1' : 'col-span-1'}`}>
        <div className="aspect-video bg-gray-100 flex items-center justify-center">
            <img src={article.image} alt={article.title} className="w-full h-full object-cover" onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
            }} />
        </div>
        <div className="p-4 bg-white">
            <span className="text-xs font-semibold text-red-600 uppercase">{article.type}</span>
            <h3 className={`mt-1 font-bold ${large ? 'text-lg' : 'text-base'} line-clamp-2`}>{article.title}</h3>
            {article.date && <p className="mt-2 text-xs text-gray-500">{article.date}</p>}
        </div>
    </div>
);

// Section Header with Pagination (페이지네이션이 있는 섹션 헤더)
const SectionHeader = ({ title, showPagination = false, hasButton = false }: { title: string; showPagination?: boolean; hasButton?: boolean }) => (
    <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl md:text-2xl font-bold text-gray-800">{title}</h2>
        {showPagination && (
            <div className="flex items-center space-x-2">
                <span className="text-gray-600 text-sm">01 / 06</span>
                <button className="p-2 border border-gray-300 rounded-full hover:bg-gray-100 transition"><ChevronLeft size={16} /></button>
                <button className="p-2 border border-gray-300 rounded-full hover:bg-gray-100 transition"><ChevronRight size={16} /></button>
            </div>
        )}
        {hasButton && (
            <button className="hidden sm:flex items-center text-sm font-medium text-white bg-black hover:bg-gray-700 transition px-6 py-3 rounded-full">
                더 많은 이야기 보러가기
            </button>
        )}
    </div>
);

// Main Application Component (메인 애플리케이션 컴포넌트)
export default function App() {
    const [activeTab, setActiveTab] = useState('전체 기사');
    const [userName, setUserName] = useState<string | null>(null);
    const [recentArticles, setRecentArticles] = useState<NewsArticle[]>([]);
    const [loading, setLoading] = useState(true);
    const router = useRouter();
    const { token, isAuthenticated, logoutAsync } = useAuth();

    // 로그인 상태 확인 및 사용자 정보 가져오기 (DB에서)
    useEffect(() => {
        const fetchUserInfo = async () => {
            if (token && isAuthenticated) {
                try {
                    // DB에서 사용자 정보 가져오기
                    const userInfo = await getCurrentUser();
                    if (userInfo && userInfo.name) {
                        setUserName(userInfo.name);
                    } else {
                        // DB에 name이 없으면 JWT에서 가져오기 (fallback)
                        const name = getUserName(token);
                        setUserName(name);
                    }
                } catch (error) {
                    console.error('사용자 정보 조회 실패:', error);
                    // API 실패 시 JWT에서 가져오기 (fallback)
                    const name = getUserName(token);
                    setUserName(name);
                }
            } else {
                setUserName(null);
            }
        };

        fetchUserInfo();
        // 주기적으로 로그인 상태 확인 (다른 탭에서 로그아웃한 경우 대비)
        // DB 조회는 비용이 있으므로 주기를 5초로 늘림
        const interval = setInterval(fetchUserInfo, 5000);
        return () => clearInterval(interval);
    }, [token, isAuthenticated]);

    // 카테고리명을 API 쿼리로 매핑하는 함수
    const getCategoryQuery = (category: string): string => {
        const categoryMap: { [key: string]: string } = {
            '전체 기사': 'latest',
            '경제': '경제',
            '정치': '정치',
            '사회': '사회',
            '문화': '문화',
            '국제/세계': '세계',
            'IT/과학': 'IT',
            '스포츠': '스포츠',
            '연예': '엔터테인먼트',
        };
        return categoryMap[category] || 'latest';
    };

    // 뉴스 데이터 가져오기 (카테고리별)
    useEffect(() => {
        const fetchNews = async () => {
            try {
                setLoading(true);
                const query = getCategoryQuery(activeTab);

                // 전체 기사는 /latest, 나머지는 /search 사용
                let apiUrl = '';
                if (query === 'latest') {
                    apiUrl = 'http://localhost:8000/api/news/latest?display=20';
                } else {
                    apiUrl = `http://localhost:8000/api/news/search?query=${encodeURIComponent(query)}&display=20`;
                }

                console.log('뉴스 API 호출:', apiUrl, '카테고리:', activeTab);
                const response = await fetch(apiUrl);

                if (!response.ok) {
                    console.error('HTTP 에러:', response.status, response.statusText);
                    const errorText = await response.text();
                    console.error('에러 응답:', errorText);
                    setRecentArticles([]);
                    return;
                }

                const data = await response.json();
                console.log('뉴스 API 응답:', data);

                if (data.success && data.articles && Array.isArray(data.articles)) {
                    setRecentArticles(data.articles);
                    console.log(`${activeTab} 카테고리 뉴스 ${data.articles.length}개 로드됨`);
                } else {
                    console.error('뉴스 데이터 가져오기 실패:', data.message || '알 수 없는 오류');
                    setRecentArticles([]);
                }
            } catch (error) {
                console.error('뉴스 API 호출 실패:', error);
                if (error instanceof Error) {
                    console.error('에러 상세:', error.message);
                }
                setRecentArticles([]);
            } finally {
                setLoading(false);
            }
        };

        fetchNews();
    }, [activeTab]); // activeTab이 변경될 때마다 새로운 데이터 가져오기

    // 로그아웃 핸들러
    const handleLogout = async () => {
        try {
            // 백엔드 API 호출 및 Zustand store에서 액세스 토큰 제거
            await logoutAsync();
        } catch (error) {
            console.error('로그아웃 처리 중 오류:', error);
        } finally {
            setUserName(null);
            router.push('/');
            router.refresh(); // 페이지 새로고침
        }
    };

    // Header Component (상단 헤더)
    const Header = () => (
        <header className="sticky top-0 z-50 bg-white shadow-md border-b border-gray-100">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
                {/* Logo */}
                <div className="flex items-center space-x-12">
                    <div className="text-xl font-extrabold text-gray-800">
                        SAMSUNG <span className="font-normal text-sm block -mt-1">Newsroom</span>
                    </div>
                    {/* Desktop Navigation */}
                    <nav className="hidden lg:flex space-x-6 text-sm">
                        {NAV_LINKS.map(link => (
                            <Link
                                key={link}
                                href={link === '트랜드 분석' ? '/trend-analysis' : link === '챗' ? '/chat' : '#'}
                                className="text-gray-600 hover:text-red-600 transition font-medium"
                            >
                                {link}
                            </Link>
                        ))}
                    </nav>
                </div>
                {/* Login & Signup Buttons, Icons & Mobile Menu */}
                <div className="flex items-center space-x-4">
                    {/* 로그인 상태에 따라 다른 UI 표시 */}
                    {isAuthenticated ? (
                        <div className="hidden lg:flex items-center space-x-3">
                            <Link
                                href="/profile"
                                className="px-4 py-2 text-sm text-gray-700 font-medium hover:text-red-600 transition cursor-pointer"
                            >
                                {userName || '사용자'}님
                            </Link>
                            <button
                                onClick={handleLogout}
                                className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 transition font-medium rounded-full"
                            >
                                로그아웃
                            </button>
                        </div>
                    ) : (
                        <div className="hidden lg:flex items-center space-x-3">
                            <Link href="/login" className="px-4 py-2 text-sm text-gray-700 hover:text-red-600 transition font-medium">
                                로그인
                            </Link>
                            <Link href="/signup" className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 transition font-medium rounded-full">
                                회원가입
                            </Link>
                        </div>
                    )}
                    <button className="p-2 text-gray-600 hover:text-red-600 transition">
                        <Search size={20} />
                    </button>
                    <button className="lg:hidden p-2 text-gray-600 hover:text-red-600 transition">
                        <AlignJustify size={20} />
                    </button>
                </div>
            </div>
        </header>
    );

    // Hero Video Component (메인 비디오 섹션)
    const HeroVideo = () => (
        <section className="bg-black mb-12">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-16">
                <div className="flex flex-col lg:flex-row space-y-8 lg:space-y-0 lg:space-x-8">
                    {/* Main Video Player Area */}
                    <div className="w-full lg:w-3/4 bg-gray-900 aspect-video flex items-center justify-center relative rounded-lg overflow-hidden">
                        <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                            <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center cursor-pointer hover:bg-white/40 transition">
                                <svg className="w-8 h-8 text-white ml-1" fill="currentColor" viewBox="0 0 24 24"><path d="M6 4l12 8-12 8z" /></svg>
                            </div>
                        </div>
                        <div className="absolute bottom-0 left-0 p-4 text-white">
                            <p className="text-xs font-light">
                                <span className="text-gray-400">01 / 04</span>
                            </p>
                            <h2 className="text-xl md:text-2xl font-bold mt-1">
                                [영상] 밸런타인 홈 오디오 룸의 실체는? 갤럭시 Z 트라이폴드 '언박싱'
                            </h2>
                        </div>
                    </div>
                    {/* Related Video Thumbnail */}
                    <div className="hidden lg:block lg:w-1/4 bg-gray-800 rounded-lg overflow-hidden relative">
                        <img
                            src="https://placehold.co/400x600/333333/FFFFFF?text=RELATED+VIDEO"
                            alt="Related Video"
                            className="w-full h-full object-cover opacity-50"
                            onError={(e) => {
                                const target = e.target as HTMLImageElement;
                                target.style.display = 'none';
                            }}
                        />
                        <div className="absolute inset-0 p-4 flex flex-col justify-end text-white">
                            <span className="text-xs text-red-400 font-semibold mb-2">[영상]</span>
                            <h3 className="text-lg font-bold line-clamp-3">
                                [영상] 삼성 비전: 미래 준비가 시작된 곳
                            </h3>
                            <div className="text-xs mt-2 text-gray-400">
                                2025.12.08
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );

    // Recent Articles Component (최신 기사 섹션)
    const RecentArticles = () => (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-16">
            <h2 className="text-2xl font-bold mb-6 border-b pb-2">최신 기사</h2>

            {/* Tabs */}
            <div className="flex overflow-x-auto space-x-4 pb-2 border-b border-gray-200 mb-8 whitespace-nowrap">
                {HEADER_LINKS.map(link => (
                    <button
                        key={link}
                        onClick={() => setActiveTab(link)}
                        disabled={loading}
                        className={`py-2 px-3 text-sm font-medium transition duration-300 ease-in-out relative ${activeTab === link
                            ? 'text-black border-b-2 border-red-600'
                            : 'text-gray-500 hover:text-red-600'
                            } ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                    >
                        {link}
                        {loading && activeTab === link && (
                            <span className="absolute -bottom-1 left-1/2 transform -translate-x-1/2">
                                <span className="flex space-x-1">
                                    <span className="w-1 h-1 bg-red-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                                    <span className="w-1 h-1 bg-red-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                                    <span className="w-1 h-1 bg-red-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                                </span>
                            </span>
                        )}
                    </button>
                ))}
            </div>

            {/* Category Info */}
            {!loading && recentArticles.length > 0 && (
                <div className="flex justify-between items-center mb-4">
                    <p className="text-sm text-gray-600">
                        <span className="font-semibold text-red-600">{activeTab}</span> 카테고리 • 총 {recentArticles.length}개의 기사
                    </p>
                    <button className="text-xs text-gray-500 hover:text-red-600 transition">
                        최신순 ▼
                    </button>
                </div>
            )}

            {/* Articles Grid */}
            {loading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                    {[...Array(8)].map((_, index) => (
                        <div key={index} className="flex flex-col rounded-lg overflow-hidden animate-pulse">
                            <div className="aspect-[4/2.5] bg-gray-200"></div>
                            <div className="p-4 bg-white">
                                <div className="h-4 bg-gray-200 rounded w-20 mb-2"></div>
                                <div className="h-5 bg-gray-200 rounded w-full mb-2"></div>
                                <div className="h-3 bg-gray-200 rounded w-24"></div>
                            </div>
                        </div>
                    ))}
                </div>
            ) : recentArticles.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                    {recentArticles.map((article, index) => (
                        <a
                            key={`${article.title}-${index}`}
                            href={article.link || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex flex-col group rounded-lg overflow-hidden hover:shadow-lg transition"
                        >
                            <div className="aspect-[4/2.5] bg-gray-100">
                                <img src={article.image} alt={article.title} className="w-full h-full object-cover" onError={(e) => {
                                    const target = e.target as HTMLImageElement;
                                    target.style.display = 'none';
                                }} />
                            </div>
                            <div className="p-4 bg-white flex flex-col flex-grow">
                                <span className="text-xs font-semibold text-red-600 uppercase">{article.type || '뉴스'}</span>
                                <h3 className="mt-1 font-bold text-base line-clamp-2 group-hover:text-red-600 transition flex-grow">{article.title}</h3>
                                <p className="mt-2 text-xs text-gray-500">{article.date || ''}</p>
                            </div>
                        </a>
                    ))}
                </div>
            ) : (
                <div className="text-center py-12">
                    <p className="text-gray-500 text-lg mb-2">
                        {activeTab === '전체 기사'
                            ? '뉴스를 불러올 수 없습니다.'
                            : `'${activeTab}' 카테고리의 뉴스가 없습니다.`}
                    </p>
                    <p className="text-gray-400 text-sm">
                        다른 카테고리를 선택하거나 잠시 후 다시 시도해주세요.
                    </p>
                </div>
            )}
        </section>
    );

    // Newsroom Pick & More Stories (뉴스룸 픽 및 더 많은 이야기 섹션)
    const NewsroomSections = () => (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-16">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Newsroom Pick (뉴스룸 픽) */}
                <div className="lg:col-span-1">
                    <h2 className="text-2xl font-bold mb-6 border-b pb-2 text-red-600">뉴스룸 픽</h2>
                    <div className="space-y-6">
                        {/* Large Pick */}
                        <div className="bg-red-600 p-6 rounded-lg text-white">
                            <h3 className="text-lg font-bold">
                                뉴스룸에서 가장 많이 읽은 이야기
                            </h3>
                            <p className="mt-2 text-sm">
                                탭 한 번으로 갤럭시Z 폴더블폰의 모든 것을 알아볼 수 있어요. 지금 확인해 보세요!
                            </p>
                            <button className="mt-4 text-sm font-medium border border-white px-4 py-2 rounded-full hover:bg-white hover:text-red-600 transition">
                                자세히 보기
                            </button>
                        </div>
                        {/* Two Smaller Picks */}
                        <div className="space-y-4">
                            <p className="text-lg font-semibold border-l-4 border-gray-300 pl-3">
                                갤럭시 Z 트라이폴드
                                <span className="block text-sm font-normal text-gray-600">완전히 새로운 모바일 경험</span>
                            </p>
                            <p className="text-lg font-semibold border-l-4 border-gray-300 pl-3">
                                밸런타인 홈 오디오 룸
                                <span className="block text-sm font-normal text-gray-600">프리미엄 스피커의 비밀</span>
                            </p>
                        </div>
                    </div>
                </div>

                {/* More Stories (더 많은 이야기) */}
                <div className="lg:col-span-2">
                    <SectionHeader title="더 많은 이야기" hasButton={true} />
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        {MORE_STORIES.map((article) => (
                            <div key={article.title} className="flex space-x-4 group">
                                <div className="flex-shrink-0 w-24 h-24 bg-gray-100 rounded-lg overflow-hidden">
                                    <img src={article.image} alt={article.title} className="w-full h-full object-cover" onError={(e) => {
                                        const target = e.target as HTMLImageElement;
                                        target.style.display = 'none';
                                    }} />
                                </div>
                                <div className="flex flex-col justify-center">
                                    <span className="text-xs font-semibold text-gray-500">{article.type}</span>
                                    <h3 className="mt-1 text-base font-bold line-clamp-2 group-hover:text-red-600 transition">{article.title}</h3>
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="mt-8 flex justify-center sm:hidden">
                        <button className="flex items-center text-sm font-medium text-white bg-black hover:bg-gray-700 transition px-6 py-3 rounded-full w-full justify-center">
                            더 많은 이야기 보러가기
                        </button>
                    </div>
                </div>
            </div>
        </section>
    );

    // Discovery/Highlight Section (확인해 보세요 및 미디어 하이라이트)


    // Footer Component (하단 푸터)
    const Footer = () => (
        <footer className="bg-gray-100 mt-12 py-8 border-t border-gray-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center space-y-4 md:space-y-0">
                    <div className="text-lg font-extrabold text-gray-800">
                        SAMSUNG
                    </div>
                    <div className="flex space-x-4 text-sm text-gray-600">
                        <a href="#" className="hover:text-red-600">이용약관</a>
                        <a href="#" className="hover:text-red-600 font-bold">개인정보처리방침</a>
                        <a href="#" className="hover:text-red-600">접근성</a>
                    </div>
                </div>
                <div className="mt-4 text-xs text-gray-500">
                    <p>Copyright © 2025 Samsung. All rights reserved.</p>
                </div>
            </div>
        </footer>
    );

    return (
        <div className="min-h-screen font-sans bg-white">
            <Header />
            <main>
                <HeroVideo />
                <RecentArticles />
                <NewsroomSections />
                {/* 확인해 보세요 */}
            </main>
            <Footer />
        </div>
    );
}
