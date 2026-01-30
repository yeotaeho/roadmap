"use client";

import React, { useState } from 'react';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Navigation, Pagination, Autoplay } from 'swiper/modules';
import type { Swiper as SwiperType } from 'swiper';
import HeroSlide, { HeroSlideData } from './HeroSlide';

// 3개의 히어로 슬라이드 데이터
const heroSlides: HeroSlideData[] = [
    {
        id: 1,
        koreanText: (
            <>
                국내외 의료진, <br />
                <span className="font-semibold text-orange-600">글로벌 파트너</span>와 함께 <br />
                <span className="font-semibold text-orange-600">지속적</span>으로 <span className="font-semibold text-orange-600">성장</span>
            </>
        ),
        englishTitle: "GROWING\nTOGETHER",
        subtitle: "TOTAL SOLUTION PROVIDER",
    },
    {
        id: 2,
        koreanText: (
            <>
                약물방출관상동맥용스텐트, <br />
                PTCA 풍선카테터 <br />
                <span className="font-semibold text-orange-600">최초로 국산화</span>
            </>
        ),
        englishTitle: "THE WAY\nOF THE PIONEER",
        subtitle: "",
    },
    {
        id: 3,
        koreanText: (
            <>
                독자적 기술력과 품질로 <br />
                혈관 질환 환자의 <br />
                <span className="font-semibold text-orange-600">삶의 질 향상</span> 추구
            </>
        ),
        englishTitle: "INNOVATIVE\nVASCULAR SOLUTIONS",
        subtitle: "THAT GO BEYOND",
    },
];

/**
 * 히어로 섹션 컴포넌트 (Swiper 슬라이더 포함)
 */
const HeroSection: React.FC = () => {
    const [swiperInstance, setSwiperInstance] = useState<SwiperType | null>(null);
    const [activeIndex, setActiveIndex] = useState(0);

    const handleSlideChange = (swiper: SwiperType) => {
        // loop 모드에서는 realIndex를 사용해야 합니다
        setActiveIndex(swiper.realIndex);
    };

    const goToSlide = (index: number) => {
        if (swiperInstance) {
            swiperInstance.slideTo(index);
        }
    };

    const goPrev = () => {
        if (swiperInstance) {
            swiperInstance.slidePrev();
        }
    };

    const goNext = () => {
        if (swiperInstance) {
            swiperInstance.slideNext();
        }
    };

    return (
        <section className="relative w-full">
            <Swiper
                modules={[Navigation, Pagination, Autoplay]}
                spaceBetween={0}
                slidesPerView={1}
                onSwiper={setSwiperInstance}
                onSlideChange={handleSlideChange}
                autoplay={{
                    delay: 5000,
                    disableOnInteraction: false,
                }}
                loop={true}
                className="hero-swiper"
            >
                {heroSlides.map((slide) => (
                    <SwiperSlide key={slide.id}>
                        <HeroSlide slide={slide} />
                    </SwiperSlide>
                ))}
            </Swiper>

            {/* 커스텀 페이지네이션 (왼쪽 텍스트 섹션 내부) */}
            <div className="absolute bottom-6 lg:bottom-8 left-6 lg:left-16 z-30 flex items-center space-x-2 text-lg font-bold text-gray-400">
                <button
                    onClick={goPrev}
                    className="cursor-pointer text-xl hover:text-black transition-colors"
                    aria-label="이전 슬라이드"
                >
                    &lt;
                </button>
                <span className="text-base lg:text-lg text-black font-extrabold w-8 text-center">
                    {String(activeIndex + 1).padStart(2, '0')}
                </span>
                <button
                    onClick={goNext}
                    className="cursor-pointer text-xl hover:text-black transition-colors"
                    aria-label="다음 슬라이드"
                >
                    &gt;
                </button>
            </div>

            {/* 스타일 추가 */}
            <style jsx global>{`
                .hero-swiper .swiper-pagination {
                    display: none;
                }
                .hero-swiper .swiper-button-next,
                .hero-swiper .swiper-button-prev {
                    display: none;
                }
            `}</style>
        </section>
    );
};

export default HeroSection;

