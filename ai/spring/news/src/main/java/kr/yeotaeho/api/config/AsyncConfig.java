package kr.yeotaeho.api.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Configuration
public class AsyncConfig {
    
    /**
     * RSS 피드 병렬 처리를 위한 ThreadPool 설정
     * 동시에 20개 RSS 피드 처리 가능
     */
    @Bean(name = "rssExecutor")
    public ExecutorService rssExecutor() {
        return Executors.newFixedThreadPool(20);
    }
}

